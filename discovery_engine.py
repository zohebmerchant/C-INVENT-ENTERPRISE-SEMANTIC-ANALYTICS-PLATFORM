"""Live Databricks / Unity Catalog discovery for C INVENT.

The discovery path intentionally uses Databricks SQL INFORMATION_SCHEMA and
DESCRIBE TABLE ... AS JSON instead of relying on the REST List Tables endpoint.
This is more portable across Databricks Free Edition/workspace versions and,
critically, DESCRIBE JSON exposes METRIC_VIEW metadata and measure columns.
"""
from __future__ import annotations
import json
import re
import pandas as pd
import streamlit as st


def _quote_ident(name: str) -> str:
    """Quote a Unity Catalog identifier safely for SQL."""
    return "`" + str(name).replace("`", "``") + "`"


def _sql_df(sql: str) -> pd.DataFrame:
    from publish_engine import get_sql_connection
    with get_sql_connection() as conn:
        return pd.read_sql(sql, conn)


def _sql_one(sql: str):
    from publish_engine import get_sql_connection
    with get_sql_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql)
        row = cur.fetchone()
        if not row:
            return None
        return row[0]


def _catalog(catalog: str) -> str:
    return _quote_ident(catalog)


def list_catalogs():
    # Information schema is privilege-aware and supported by Unity Catalog.
    df = _sql_df("SELECT catalog_name FROM system.information_schema.catalogs ORDER BY catalog_name")
    return [x for x in df.get("catalog_name", pd.Series(dtype=str)).dropna().astype(str).tolist()]


def list_schemas(catalog):
    c = _catalog(catalog)
    q = f"""
        SELECT schema_name, schema_owner, comment, created, last_altered
        FROM {c}.information_schema.schemata
        ORDER BY schema_name
    """
    return _sql_df(q)


def list_tables(catalog, schema=None):
    c = _catalog(catalog)
    where = ""
    if schema:
        safe_schema = str(schema).replace("'", "''")
        where = f"WHERE table_schema = '{safe_schema}'"
    q = f"""
        SELECT
            table_catalog AS catalog_name,
            table_schema AS schema_name,
            table_name AS name,
            CONCAT(table_catalog, '.', table_schema, '.', table_name) AS full_name,
            table_type,
            is_insertable_into
        FROM {c}.information_schema.tables
        {where}
        ORDER BY table_schema, table_name
    """
    df = _sql_df(q)
    if df.empty:
        return df
    # Keep the UI columns stable while making ownership/comment available
    # through DESCRIBE when the object is inspected.
    df["owner"] = None
    df["comment"] = None
    return df


def _describe_json(full_name: str):
    """Return Databricks DESCRIBE EXTENDED ... AS JSON metadata."""
    # full_name comes from Unity Catalog metadata, not user-entered SQL.
    parts = str(full_name).split(".")
    if len(parts) != 3:
        raise ValueError(f"Expected catalog.schema.object, got: {full_name}")
    ident = ".".join(_quote_ident(p) for p in parts)
    from publish_engine import get_sql_connection
    with get_sql_connection() as conn:
        cur = conn.cursor()
        cur.execute(f"DESCRIBE TABLE EXTENDED {ident} AS JSON")
        row = cur.fetchone()
        if not row:
            return {}
        raw = row[0]
        if isinstance(raw, (bytes, bytearray)):
            raw = raw.decode("utf-8")
        if isinstance(raw, dict):
            return raw
        return json.loads(str(raw))


def _enrich_table_metadata(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    # DESCRIBE is deliberately used only for candidate views / metric views.
    candidates = out[
        out["table_type"].astype(str).str.upper().isin(["VIEW", "METRIC_VIEW", "MATERIALIZED_VIEW"])
        | out["name"].astype(str).str.lower().str.startswith("mv_")
    ]
    for idx, row in candidates.iterrows():
        try:
            meta = _describe_json(row["full_name"])
            out.at[idx, "table_type"] = meta.get("type") or row["table_type"]
            out.at[idx, "owner"] = meta.get("owner")
            out.at[idx, "comment"] = meta.get("comment")
        except Exception:
            # Discovery should not fail because one object cannot be described.
            continue
    return out


def list_columns(catalog, schema=None):
    c = _catalog(catalog)
    where = ""
    if schema:
        safe_schema = str(schema).replace("'", "''")
        where = f"WHERE table_schema = '{safe_schema}'"
    q = f"""
        SELECT table_schema, table_name, column_name, ordinal_position,
               data_type, is_nullable, comment
        FROM {c}.information_schema.columns
        {where}
        ORDER BY table_schema, table_name, ordinal_position
    """
    return _sql_df(q)


def list_relationships(catalog):
    """Return declared Unity Catalog FK -> PK/UNIQUE relationships."""
    c = _catalog(catalog)
    try:
        q = f"""
        SELECT
            k.table_schema AS fk_schema,
            k.table_name AS fk_table,
            k.column_name AS fk_column,
            r.unique_constraint_schema AS pk_schema,
            u.table_name AS pk_table,
            u.column_name AS pk_column,
            k.constraint_name
        FROM {c}.information_schema.key_column_usage k
        JOIN {c}.information_schema.table_constraints tc
          ON k.constraint_catalog = tc.constraint_catalog
         AND k.constraint_schema = tc.constraint_schema
         AND k.constraint_name = tc.constraint_name
        JOIN {c}.information_schema.referential_constraints r
          ON k.constraint_catalog = r.constraint_catalog
         AND k.constraint_schema = r.constraint_schema
         AND k.constraint_name = r.constraint_name
        JOIN {c}.information_schema.key_column_usage u
          ON u.constraint_catalog = r.unique_constraint_catalog
         AND u.constraint_schema = r.unique_constraint_schema
         AND u.constraint_name = r.unique_constraint_name
         AND u.position_in_unique_constraint = k.position_in_unique_constraint
        WHERE tc.constraint_type = 'FOREIGN KEY'
        ORDER BY k.table_schema, k.table_name, k.column_name
        """
        return _sql_df(q)
    except Exception:
        # FK metadata is preview/privilege dependent. Discovery remains useful
        # even when the workspace exposes no constraint metadata.
        return pd.DataFrame(columns=[
            "fk_schema", "fk_table", "fk_column",
            "pk_schema", "pk_table", "pk_column", "constraint_name"
        ])


def discover_catalog(catalog):
    schemas = list_schemas(catalog)
    tables = _enrich_table_metadata(list_tables(catalog))
    metrics = tables[tables["table_type"].astype(str).str.upper().eq("METRIC_VIEW")].copy() if not tables.empty else pd.DataFrame()
    if not metrics.empty:
        metrics["kind"] = "Metric View"
    columns = list_columns(catalog)
    relationships = list_relationships(catalog)
    return {
        "catalog": catalog,
        "schemas": schemas,
        "tables": tables,
        "metric_views": metrics,
        "columns": columns,
        "relationships": relationships,
    }


def get_table(full_name):
    return _describe_json(full_name)


def metric_view_details(full_name):
    info = _describe_json(full_name)
    cols = []
    for c in info.get("columns", []) or []:
        typ = c.get("type")
        if isinstance(typ, dict):
            typ = typ.get("name", str(typ))
        cols.append({
            "name": c.get("name"),
            "type": typ,
            "nullable": c.get("nullable"),
            "is_measure": bool(c.get("is_measure", False)),
            "comment": c.get("comment"),
        })
    return {
        "full_name": full_name,
        "table_type": info.get("type"),
        "columns": pd.DataFrame(cols),
        "comment": info.get("comment"),
        "owner": info.get("owner"),
        "view_definition": info.get("view_text") or info.get("view_original_text"),
        "language": info.get("language"),
    }


def query(sql):
    return _sql_df(sql)

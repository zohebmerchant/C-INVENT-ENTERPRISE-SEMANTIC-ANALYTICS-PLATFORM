"""
Enterprise Semantic Analytics Platform — Metadata Registry.

Persistent metadata contract between the published semantic model,
Analytics and Ask AI.

Genie is optional.  The registry can store a Genie Space ID when one is
configured, but publishing never depends on the Genie management API.
This keeps Databricks Free Edition + PAT publication reliable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import streamlit as st

from publish_engine import get_sql_connection


REGISTRY_SCHEMA = "platform_registry"
REGISTRY_TABLE = "metadata_registry"


@dataclass
class RegistryEntry:
    domain_name: str
    catalog: str
    schema: str
    metric_view: str
    fact_table: str
    measures: list
    dimensions: list
    default_kpi: str
    row_count: int
    published_at: str
    genie_space_id: str | None = None
    fact_tables: list[str] | None = None


def _registry_table() -> str:
    catalog = st.secrets["DATABRICKS_CATALOG"]
    return f"{catalog}.{REGISTRY_SCHEMA}.{REGISTRY_TABLE}"


def ensure_registry_exists():
    """
    Create the registry and migrate older installations.

    Existing deployments may not contain genie_space_id, so the column
    is added automatically.
    """
    catalog = st.secrets["DATABRICKS_CATALOG"]
    full_table = _registry_table()

    with get_sql_connection() as conn:
        with conn.cursor() as cur:

            cur.execute(
                f"CREATE SCHEMA IF NOT EXISTS "
                f"{catalog}.{REGISTRY_SCHEMA}"
            )

            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {full_table} (
                    domain_name STRING,
                    catalog_name STRING,
                    schema_name STRING,
                    metric_view STRING,
                    fact_table STRING,
                    measures_json STRING,
                    dimensions_json STRING,
                    default_kpi STRING,
                    row_count BIGINT,
                    published_at STRING,
                    genie_space_id STRING,
                    fact_tables_json STRING,
                    fact_count BIGINT
                )
                USING DELTA
                """
            )

            cur.execute(
                f"DESCRIBE TABLE {full_table}"
            )

            columns = {
                str(row[0]).lower()
                for row in cur.fetchall()
                if row and row[0]
            }

            if "genie_space_id" not in columns:
                cur.execute(f"ALTER TABLE {full_table} ADD COLUMNS (genie_space_id STRING)")
            if "fact_tables_json" not in columns:
                cur.execute(f"ALTER TABLE {full_table} ADD COLUMNS (fact_tables_json STRING)")
            if "fact_count" not in columns:
                cur.execute(f"ALTER TABLE {full_table} ADD COLUMNS (fact_count BIGINT)")

        conn.commit()


def register_domain(entry: RegistryEntry):
    """
    Upsert a domain registry row.

    The Genie ID is persisted when an Agent is connected or created; publication remains resilient if Genie is unavailable.
    """
    ensure_registry_exists()

    full_table = _registry_table()

    measures_json = json.dumps(
        entry.measures,
        ensure_ascii=False,
        default=str,
    )

    dimensions_json = json.dumps(
        entry.dimensions,
        ensure_ascii=False,
        default=str,
    )
    fact_tables_json = json.dumps(entry.fact_tables or [entry.fact_table], ensure_ascii=False)

    with get_sql_connection() as conn:
        with conn.cursor() as cur:

            cur.execute(
                f"""
                DELETE FROM {full_table}
                WHERE domain_name = ?
                """,
                (entry.domain_name,),
            )

            cur.execute(
                f"""
                INSERT INTO {full_table}
                (
                    domain_name,
                    catalog_name,
                    schema_name,
                    metric_view,
                    fact_table,
                    measures_json,
                    dimensions_json,
                    default_kpi,
                    row_count,
                    published_at,
                    genie_space_id,
                    fact_tables_json,
                    fact_count
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.domain_name,
                    entry.catalog,
                    entry.schema,
                    entry.metric_view,
                    entry.fact_table,
                    measures_json,
                    dimensions_json,
                    entry.default_kpi,
                    int(entry.row_count),
                    entry.published_at,
                    entry.genie_space_id,
                    fact_tables_json,
                    len(entry.fact_tables or [entry.fact_table]),
                ),
            )

        conn.commit()


def list_domains() -> list[RegistryEntry]:
    """
    Return all published domains.

    Handles older rows where genie_space_id is NULL.
    """
    try:
        ensure_registry_exists()

        full_table = _registry_table()

        with get_sql_connection() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    f"""
                    SELECT
                        domain_name,
                        catalog_name,
                        schema_name,
                        metric_view,
                        fact_table,
                        measures_json,
                        dimensions_json,
                        default_kpi,
                        row_count,
                        published_at,
                        genie_space_id,
                        fact_tables_json,
                        fact_count
                    FROM {full_table}
                    ORDER BY published_at DESC
                    """
                )

                rows = cur.fetchall()

        entries = []

        for row in rows:

            (
                domain_name,
                catalog_name,
                schema_name,
                metric_view,
                fact_table,
                measures_json,
                dimensions_json,
                default_kpi,
                row_count,
                published_at,
                genie_space_id,
                fact_tables_json,
                fact_count,
            ) = row

            try:
                measures = json.loads(
                    measures_json or "[]"
                )
            except Exception:
                measures = []

            try:
                dimensions = json.loads(
                    dimensions_json or "[]"
                )
            except Exception:
                dimensions = []

            try:
                fact_tables = json.loads(fact_tables_json or "[]")
                if not isinstance(fact_tables, list):
                    fact_tables = []
            except Exception:
                fact_tables = []
            if not fact_tables and fact_table:
                fact_tables = [fact_table]

            entries.append(
                RegistryEntry(
                    domain_name=domain_name,
                    catalog=catalog_name,
                    schema=schema_name,
                    metric_view=metric_view,
                    fact_table=fact_table,
                    measures=measures,
                    dimensions=dimensions,
                    default_kpi=default_kpi,
                    row_count=int(row_count or 0),
                    published_at=published_at,
                    genie_space_id=genie_space_id or None,
                    fact_tables=fact_tables,
                )
            )

        return entries

    except Exception:
        return []


def get_domain(domain_name: str) -> RegistryEntry | None:
    for entry in list_domains():
        if entry.domain_name == domain_name:
            return entry
    return None


def get_genie_space_id(domain_name: str) -> str | None:
    entry = get_domain(domain_name)
    return entry.genie_space_id if entry else None

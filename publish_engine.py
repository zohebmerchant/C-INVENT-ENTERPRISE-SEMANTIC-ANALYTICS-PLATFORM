"""C INVENT production publish engine.

One domain publish creates:
- one schema
- one Delta table for every detected source table
- one canonical domain Metric View: mv_domain
- one domain-scoped Genie Agent

All detected facts remain real Delta tables.  The canonical Metric View is
built over a generated union source so measures from every fact are available
through the single governed analytics entry point without unsafe fact-to-fact
fan-out.
"""
from __future__ import annotations
import re
from collections import deque
import pandas as pd
import streamlit as st
from databricks import sql as dbsql
import security_fabric as security
from semantic_engine import SemanticModel, _looks_like_id_column, _looks_non_additive, _looks_like_rating_or_category_column


def _sanitize_identifier(name: str) -> str:
    n = re.sub(r'\.(csv|xlsx?|xls|json|parquet|xml)$', '', name, flags=re.I)
    n = re.sub(r'[^a-zA-Z0-9_]', '_', n).lower()
    n = re.sub(r'_+', '_', n).strip('_')
    return n or 'table'


def _validate_domain_schema_name(domain_name: str) -> str:
    return f"domain_{_sanitize_identifier(domain_name)}"


def get_sql_connection():
    hostname = st.secrets['DATABRICKS_HOST'].replace('https://','').replace('http://','')
    cfg = security._pat_config()
    return dbsql.connect(
        server_hostname=hostname,
        http_path=f"/sql/1.0/warehouses/{st.secrets['DATABRICKS_WAREHOUSE_ID']}",
        credentials_provider=lambda: cfg.authenticate,
        catalog=st.secrets['DATABRICKS_CATALOG'],
    )


def _infer_sql_type(series: pd.Series) -> str:
    dtype = str(series.dtype).lower()
    if 'datetime' in dtype:
        return 'TIMESTAMP'
    if 'bool' in dtype:
        return 'BOOLEAN'
    if 'int' in dtype:
        return 'BIGINT'
    if 'float' in dtype:
        return 'DOUBLE'
    return 'STRING'


def _write_dataframe_as_table(cursor, df: pd.DataFrame, full_table_name: str, max_rows_inline: int = 2000):
    if len(df) > max_rows_inline:
        raise ValueError(f"{full_table_name}: {len(df)} rows exceeds the inline publish limit of {max_rows_inline}. Use a Volume/COPY INTO path for production-scale ingestion.")
    cols_ddl = ', '.join(f"`{c}` {_infer_sql_type(df[c])}" for c in df.columns)
    cursor.execute(f"DROP TABLE IF EXISTS {full_table_name}")
    cursor.execute(f"CREATE TABLE {full_table_name} ({cols_ddl}) USING DELTA")
    if len(df) == 0:
        return
    col_names = ', '.join(f"`{c}`" for c in df.columns)
    rows = []
    for _, row in df.iterrows():
        vals=[]
        for v in row:
            if pd.isna(v): vals.append('NULL')
            elif isinstance(v, bool): vals.append('TRUE' if v else 'FALSE')
            elif isinstance(v, (int,float)): vals.append(str(v))
            else: vals.append("'"+str(v).replace("'","''")+"'")
        rows.append('('+', '.join(vals)+')')
    cursor.execute(f"INSERT INTO {full_table_name} ({col_names}) VALUES {', '.join(rows)}")


def _dtype_sql(profile, col):
    for c in profile.columns:
        if c.name == col:
            return _dtype_to_sql(c.dtype)
    return 'STRING'


def _dtype_to_sql(dtype: str) -> str:
    d = dtype.lower()
    if 'datetime' in d: return 'TIMESTAMP'
    if 'bool' in d: return 'BOOLEAN'
    if 'int' in d: return 'BIGINT'
    if 'float' in d or 'double' in d: return 'DOUBLE'
    if 'date' in d: return 'DATE'
    return 'STRING'


def _relationship_path(model: SemanticModel, start: str, target: str):
    """Find a safe FK->PK path from a fact to a dimension.

    Only N:1 edges are traversed. Dimensions are terminal nodes. This lets
    booking_services -> bookings -> customers work without joining two facts
    into the metric aggregation directly.
    """
    if start == target:
        return []
    adjacency={t:[] for t in model.tables}
    for r in model.relationships:
        if r.is_many_to_many:
            continue
        adjacency.setdefault(r.from_table, []).append(r)
    q=deque([(start,[])])
    seen={start}
    while q:
        node,path=q.popleft()
        for r in adjacency.get(node,[]):
            if r.to_table in seen: continue
            np=path+[r]
            if r.to_table == target:
                return np
            # Never walk outward from a dimension; dimensions are leaves.
            if r.to_table in model.dimensions:
                continue
            seen.add(r.to_table)
            q.append((r.to_table,np))
    return None


def _metric_names_for_fact(model, fact):
    profile=model.tables[fact]
    related_fk={r.from_column for r in model.relationships if r.from_table==fact}
    measures=[]
    for c in profile.columns:
        if c.name in related_fk or c.null_pct>=100: continue
        is_id=_looks_like_id_column(c.name,c.dtype)
        is_rating=_looks_like_rating_or_category_column(c,profile.row_count)
        if ('int' in c.dtype.lower() or 'float' in c.dtype.lower()) and not is_id and not is_rating:
            agg='AVG' if _looks_non_additive(c.name) else 'SUM'
            base=f"{agg.lower()}_{c.name}" if agg=='AVG' else f"total_{c.name}"
            measures.append((base,c.name,agg))
    measures.append((f"{_sanitize_identifier(fact)}_count",None,'COUNT'))
    return measures


def _build_domain_source_sql(model: SemanticModel, catalog: str, schema: str, primary_fact: str):
    """Build one UNION ALL source relation with all facts and conformed dims.

    Every row carries fact_type and a one-hot row counter. Fact measures are
    kept separate, preventing cross-fact aggregation errors while exposing all
    fact metrics through one canonical Metric View.
    """
    facts=list(model.facts)
    dims=list(model.dimensions)
    fact_cols=[]
    for f in facts:
        for c in model.tables[f].columns:
            fact_cols.append((f,c.name,_dtype_sql(model.tables[f],c.name)))
    dim_cols=[]
    for d in dims:
        for c in model.tables[d].columns:
            dim_cols.append((d,c.name,_dtype_sql(model.tables[d],c.name)))

    branches=[]
    for fact in facts:
        f_alias='f0'
        joins=[]
        aliases={fact:f_alias}
        paths={}
        for d in dims:
            path=_relationship_path(model,fact,d)
            if path is None: continue
            cur=fact
            for r in path:
                # Advance the current relation even when an intermediate table
                # was already joined. Without this, a path such as
                # order_items -> orders -> stores incorrectly generated
                # `f0.store_id` instead of `j1.store_id`, causing
                # UNRESOLVED_COLUMN at publish time.
                if r.to_table in aliases:
                    cur = r.to_table
                    continue
                alias=f"j{len(aliases)}"
                aliases[r.to_table]=alias
                left_alias=aliases[cur]
                joins.append(
                    f"LEFT JOIN {catalog}.{schema}.{_sanitize_identifier(r.to_table)} {alias} "
                    f"ON {left_alias}.`{r.from_column}` = {alias}.`{r.to_column}`"
                )
                cur=r.to_table
            paths[d]=aliases[d]
        select=[f"'{_sanitize_identifier(fact)}' AS fact_type"]
        for f,c,typ in fact_cols:
            alias=aliases.get(f)
            out=f"f_{_sanitize_identifier(f)}_{_sanitize_identifier(c)}"
            if alias:
                select.append(f"CAST({alias}.`{c}` AS {typ}) AS `{out}`")
            else:
                select.append(f"CAST(NULL AS {typ}) AS `{out}`")
        for d,c,typ in dim_cols:
            out=f"d_{_sanitize_identifier(d)}_{_sanitize_identifier(c)}"
            alias=paths.get(d)
            if alias:
                select.append(f"CAST({alias}.`{c}` AS {typ}) AS `{out}`")
            else:
                select.append(f"CAST(NULL AS {typ}) AS `{out}`")
        for f in facts:
            counter=f"__row_count_{_sanitize_identifier(f)}"
            select.append(f"CAST({'1' if f==fact else '0'} AS BIGINT) AS `{counter}`")
        branches.append("SELECT\n  "+",\n  ".join(select)+f"\nFROM {catalog}.{schema}.{_sanitize_identifier(fact)} {f_alias}\n"+"\n".join(joins))
    return "\nUNION ALL\n".join(branches)


def _build_metric_yaml(model, catalog, schema, source_name, primary_fact):
    fields=[]
    measures=[]
    dimensions=[]
    for d in model.dimensions:
        for c in model.tables[d].columns:
            name=f"{_sanitize_identifier(d)}_{_sanitize_identifier(c.name)}"
            source=f"d_{_sanitize_identifier(d)}_{_sanitize_identifier(c.name)}"
            fields.append(f"  - name: {name}\n    expr: source.`{source}`")
            dimensions.append(name)
    fields.append("  - name: fact_type\n    expr: source.fact_type")

    for fact in model.facts:
        prefix=_sanitize_identifier(fact)
        for idx,(name,col,agg) in enumerate(_metric_names_for_fact(model,fact)):
            if col is None:
                source=f"__row_count_{prefix}"
                measures.append(f"  - name: {name}\n    expr: SUM(source.`{source}`)")
            else:
                # Preserve the primary fact's clean names; namespace other facts.
                public=name if fact==primary_fact else f"{prefix}_{name}"
                source=f"f_{prefix}_{_sanitize_identifier(col)}"
                measures.append(f"  - name: {public}\n    expr: {agg}(source.`{source}`)")
    yaml=f"""version: 1.1\nsource: {catalog}.{schema}.{source_name}\ncomment: \"C INVENT canonical domain Metric View — {model.domain_name}; all detected facts\"\n\njoins:\n  []\n\nfields:\n{chr(10).join(fields) if fields else '  []'}\n\nmeasures:\n{chr(10).join(measures) if measures else '  []'}\n"""
    measure_names=[]
    for fact in model.facts:
        for name,col,agg in _metric_names_for_fact(model,fact):
            measure_names.append(name if fact==primary_fact else f"{_sanitize_identifier(fact)}_{name}" if col is not None else name)
    return yaml,measure_names,dimensions


def publish_domain(model: SemanticModel, fact_table: str, genie_space_id: str|None=None, reader_principal: str|None=None) -> dict:
    catalog=st.secrets['DATABRICKS_CATALOG']
    schema=_validate_domain_schema_name(model.domain_name)
    if fact_table not in model.facts: raise ValueError(f"'{fact_table}' is not a governed fact table.")
    created=[]
    source_name='_invent_mv_domain_source'
    canonical=f"{catalog}.{schema}.mv_domain"
    source_full=f"{catalog}.{schema}.{source_name}"
    with get_sql_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}")
            for table_name,profile in model.tables.items():
                full=f"{catalog}.{schema}.{_sanitize_identifier(table_name)}"
                _write_dataframe_as_table(cur,profile.df,full)
                created.append(full)
            source_sql=_build_domain_source_sql(model,catalog,schema,fact_table)
            cur.execute(f"CREATE OR REPLACE VIEW {source_full} AS {source_sql}")
            yaml,measure_names,dimension_names=_build_metric_yaml(model,catalog,schema,source_name,fact_table)
            cur.execute(f"CREATE OR REPLACE VIEW {canonical} WITH METRICS LANGUAGE YAML AS $${yaml}$$")
            # Remove legacy per-fact Metric Views only. Never drop source Delta tables.
            for legacy_fact in model.facts:
                legacy=f"{catalog}.{schema}.mv_{_sanitize_identifier(legacy_fact)}"
                if legacy != canonical:
                    try: cur.execute(f"DROP VIEW IF EXISTS {legacy}")
                    except Exception: pass
    actions=[]
    if reader_principal:
        actions.append(security.grant_select_on_schema(f"{catalog}.{schema}",reader_principal))
    primary=next((m for m in measure_names if m), None)
    questions=[f"What are the key KPIs for {model.domain_name}?", f"Show {primary or 'the main KPI'} by the main business dimensions."]
    resolved,action=security.register_table_with_genie_space(
        genie_space_id,
        table_full_name=f"{catalog}.{schema}.{_sanitize_identifier(fact_table)}",
        metric_view_full_name=canonical,
        domain_name=model.domain_name,
        measures=measure_names,
        dimensions=dimension_names,
        sample_questions=questions,
    )
    actions.append(action)
    return {
        'catalog':catalog,'schema':schema,'tables_created':created,
        'metric_view':canonical,'metric_views':{f:{'metric_view':canonical,'measures':measure_names,'dimensions':dimension_names} for f in model.facts},
        'measures':measure_names,'dimensions':dimension_names,'fact_tables':list(model.facts),
        'genie_space_id':resolved,'security_actions':actions,'source_view':source_full,
    }

"""
Enterprise Semantic Analytics Platform
--------------------------------------

Metadata-driven analytics engine.

IMPORTANT ARCHITECTURE PRINCIPLE
---------------------------------
This module contains NO domain-specific logic.

It consumes RegistryEntry objects produced by registry.py and dynamically
renders analytics from:

    RegistryEntry
        |
        +-- domain_name
        +-- metric_view
        +-- fact_table
        +-- measures
        +-- dimensions
        +-- default_kpi
        +-- row_count
        +-- published_at
        |
        v
    Databricks Metric View
        |
        v
    Metadata-driven Analytics

The same code therefore works for:

    Healthcare
    Finance
    Retail
    Banking
    Insurance
    Manufacturing
    Telecom
    etc.

No domain-specific SQL is hardcoded here.
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd
import streamlit as st

from registry import list_domains


# =============================================================================
# REGISTRY HELPERS
# =============================================================================


def _entry_get(entry: Any, field: str, default=None):
    """
    Safely read a field from either:

        RegistryEntry dataclass/object

    or:

        dictionary

    This makes the analytics layer tolerant of minor registry
    implementation differences.
    """

    if entry is None:
        return default

    if isinstance(entry, dict):
        return entry.get(field, default)

    return getattr(entry, field, default)


def _entry_domain_name(entry: Any) -> str:
    return str(
        _entry_get(
            entry,
            "domain_name",
            "Unknown Domain",
        )
    )


def _entry_metric_view(entry: Any) -> str:
    return str(
        _entry_get(
            entry,
            "metric_view",
            "",
        )
    )


def _entry_measures(entry: Any) -> list[str]:
    measures = _entry_get(entry, "measures", [])

    if not measures:
        return []

    return [
        str(x).strip()
        for x in measures
        if str(x).strip()
    ]


def _entry_dimensions(entry: Any) -> list[str]:
    dimensions = _entry_get(entry, "dimensions", [])

    if not dimensions:
        return []

    return [
        str(x).strip()
        for x in dimensions
        if str(x).strip()
    ]


# =============================================================================
# DOMAIN RESOLUTION
# =============================================================================


def _resolve_domain_entry(domain: Any):
    """
    Resolve the selected domain into the actual RegistryEntry.

    Supports ALL of these:

        render_domain_dashboard("Healthcare")

        render_domain_dashboard(registry_entry)

        render_domain_dashboard({"domain_name": "Healthcare", ...})

    The previous implementation incorrectly assumed the argument was
    always a string. Your 5_Analytics.py is passing the actual RegistryEntry,
    which caused:

        Domain 'RegistryEntry(...)' is not present...

    This function fixes that.
    """

    if domain is None:
        return None

    # -------------------------------------------------------------------------
    # Case 1:
    # Already a RegistryEntry object.
    # -------------------------------------------------------------------------
    if not isinstance(domain, str):
        domain_name = _entry_get(domain, "domain_name")

        if domain_name:
            return domain

    # -------------------------------------------------------------------------
    # Case 2:
    # Domain name string.
    # -------------------------------------------------------------------------
    domain_name = str(domain).strip()

    if not domain_name:
        return None

    try:
        domains = list_domains()
    except Exception:
        return None

    for entry in domains or []:
        if _entry_domain_name(entry).lower() == domain_name.lower():
            return entry

    return None


# =============================================================================
# SQL SAFETY
# =============================================================================


def _validate_identifier(value: str, label: str = "identifier") -> str:
    """
    Validate identifiers coming from the governed registry.

    We do not allow arbitrary SQL fragments to be injected into
    generated analytics queries.
    """

    value = str(value or "").strip()

    if not value:
        raise ValueError(f"Empty {label}.")

    # Allow:
    #
    # catalog.schema.view
    # table.column
    # metric_name
    #
    # but no SQL operators, quotes, spaces, comments, etc.
    if not re.fullmatch(
        r"[A-Za-z0-9_.$]+",
        value,
    ):
        raise ValueError(
            f"Unsafe {label}: {value!r}"
        )

    return value


def _quote_identifier(value: str, label: str = "identifier") -> str:
    """
    Convert a metadata identifier into a Databricks SQL quoted identifier.

    Example:

        patient_name
            ->
        `patient_name`
    """

    value = _validate_identifier(
        value,
        label,
    )

    # Quote each identifier component separately.
    #
    # catalog.schema.view
    #
    # becomes:
    #
    # `catalog`.`schema`.`view`
    #
    parts = value.split(".")

    return ".".join(
        f"`{part}`"
        for part in parts
    )


# =============================================================================
# DATABRICKS CONNECTION
# =============================================================================


def _get_sql_connection():
    """
    Reuse the application's existing Databricks SQL connection.

    Authentication remains centralized in publish_engine.py.

    Analytics does NOT create another authentication mechanism.
    """

    from publish_engine import get_sql_connection

    return get_sql_connection()


def _execute_query(sql: str) -> pd.DataFrame:
    """
    Execute one read-only analytical query.
    """

    sql = str(sql).strip()

    if not sql:
        raise ValueError("Empty SQL query.")

    upper = sql.upper()

    # -------------------------------------------------------------------------
    # Basic read-only protection.
    # -------------------------------------------------------------------------

    if not (
        upper.startswith("SELECT")
        or upper.startswith("WITH")
    ):
        raise ValueError(
            "Analytics query must be read-only."
        )

    # No multiple statements.
    stripped = sql.rstrip(";")

    if ";" in stripped:
        raise ValueError(
            "Multiple SQL statements are not allowed."
        )

    forbidden = [
        " INSERT ",
        " UPDATE ",
        " DELETE ",
        " MERGE ",
        " DROP ",
        " ALTER ",
        " CREATE ",
        " TRUNCATE ",
        " GRANT ",
        " REVOKE ",
        " CALL ",
    ]

    padded = f" {upper} "

    for keyword in forbidden:
        if keyword in padded:
            raise ValueError(
                f"Forbidden SQL operation detected: {keyword.strip()}"
            )

    # -------------------------------------------------------------------------
    # Execute.
    # -------------------------------------------------------------------------

    with _get_sql_connection() as conn:

        with conn.cursor() as cursor:

            cursor.execute(sql)

            rows = cursor.fetchall()

            description = cursor.description or []

            columns = [
                column[0]
                for column in description
            ]

    return pd.DataFrame(
        rows,
        columns=columns,
    )


# =============================================================================
# METRIC VIEW SQL
# =============================================================================


def _measure_expression(measure: str) -> str:
    """
    Generate a Metric View measure expression.

    Databricks Metric View syntax:

        MEASURE(`measure_name`)
    """

    measure = _validate_identifier(
        measure,
        "measure",
    )

    return f"MEASURE(`{measure}`)"


def _dimension_expression(dimension: str) -> str:
    """
    Generate a safe dimension expression.
    """

    dimension = _validate_identifier(
        dimension,
        "dimension",
    )

    return f"`{dimension}`"


def _metric_view_expression(entry: Any) -> str:
    """
    Get the fully qualified Metric View from the registry.
    """

    metric_view = _entry_metric_view(entry)

    if not metric_view:
        raise ValueError(
            f"No Metric View registered for "
            f"domain '{_entry_domain_name(entry)}'."
        )

    return _quote_identifier(
        metric_view,
        "Metric View",
    )


# =============================================================================
# VALUE FORMATTING
# =============================================================================


def _format_value(value: Any) -> str:

    if value is None:
        return "—"

    try:

        if pd.isna(value):
            return "—"

    except Exception:
        pass

    # Integer
    if isinstance(value, int):
        return f"{value:,}"

    # Float
    if isinstance(value, float):

        absolute = abs(value)

        if absolute >= 1_000_000_000:
            return f"{value / 1_000_000_000:.2f}B"

        if absolute >= 1_000_000:
            return f"{value / 1_000_000:.2f}M"

        if absolute >= 1_000:
            return f"{value / 1_000:.1f}K"

        return f"{value:,.2f}"

    # Numeric values from numpy / Decimal etc.
    try:

        numeric = float(value)

        if numeric.is_integer():
            return f"{int(numeric):,}"

        absolute = abs(numeric)

        if absolute >= 1_000_000_000:
            return f"{numeric / 1_000_000_000:.2f}B"

        if absolute >= 1_000_000:
            return f"{numeric / 1_000_000:.2f}M"

        if absolute >= 1_000:
            return f"{numeric / 1_000:.1f}K"

        return f"{numeric:,.2f}"

    except Exception:
        return str(value)


def _pretty_name(value: str) -> str:

    value = str(value)

    value = value.replace("_", " ")

    return value.title()


# =============================================================================
# KPI CALCULATIONS
# =============================================================================


def _calculate_measure(
    entry: Any,
    measure: str,
) -> Any:

    metric_view = _metric_view_expression(entry)

    measure_expression = _measure_expression(
        measure
    )

    sql = f"""
SELECT
    {measure_expression} AS metric_value
FROM {metric_view}
"""

    result = _execute_query(sql)

    if result.empty:
        return None

    return result.iloc[0]["metric_value"]


def _render_kpis(entry: Any):

    measures = _entry_measures(entry)

    if not measures:

        st.info(
            "No governed measures are registered "
            "for this domain."
        )

        return

    st.markdown(
        "### Key Metrics"
    )

    # Maximum four cards in the first row.
    selected_measures = measures[:4]

    columns = st.columns(
        len(selected_measures)
    )

    for column, measure in zip(
        columns,
        selected_measures,
    ):

        try:

            value = _calculate_measure(
                entry,
                measure,
            )

            with column:

                st.metric(
                    label=_pretty_name(
                        measure
                    ),
                    value=_format_value(
                        value
                    ),
                )

        except Exception as exc:

            with column:

                st.metric(
                    label=_pretty_name(
                        measure
                    ),
                    value="—",
                )

                st.caption(
                    f"Unable to calculate: {exc}"
                )


# =============================================================================
# DEFAULT BUSINESS ANALYSIS
# =============================================================================


def _run_dimension_measure_analysis(
    entry: Any,
    dimension: str,
    measure: str,
    limit: int = 15,
) -> pd.DataFrame:

    metric_view = _metric_view_expression(
        entry
    )

    dimension_expression = _dimension_expression(
        dimension
    )

    measure_expression = _measure_expression(
        measure
    )

    # limit is generated internally, not supplied by the user.
    limit = max(
        1,
        min(
            int(limit),
            100,
        ),
    )

    sql = f"""
SELECT
    {dimension_expression} AS dimension_value,
    {measure_expression} AS metric_value
FROM {metric_view}
GROUP BY
    {dimension_expression}
ORDER BY
    metric_value DESC
LIMIT {limit}
"""

    return _execute_query(sql)


def _render_default_analysis(entry: Any):

    dimensions = _entry_dimensions(
        entry
    )

    measures = _entry_measures(
        entry
    )

    if not dimensions:

        st.info(
            "No governed dimensions are registered "
            "for this domain."
        )

        return

    if not measures:

        st.info(
            "No governed measures are registered "
            "for this domain."
        )

        return

    dimension = dimensions[0]

    measure = measures[0]

    st.markdown(
        "### Automatic Business Analysis"
    )

    st.caption(
        f"Analyzing "
        f"**{_pretty_name(measure)}** "
        f"by "
        f"**{_pretty_name(dimension)}**"
    )

    try:

        result = _run_dimension_measure_analysis(
            entry,
            dimension,
            measure,
            limit=15,
        )

        if result.empty:

            st.info(
                "No analytical data was returned."
            )

            return

        chart_data = result.copy()

        chart_data["dimension_value"] = (
            chart_data[
                "dimension_value"
            ]
            .fillna("Unknown")
            .astype(str)
        )

        chart_data = chart_data.set_index(
            "dimension_value"
        )

        st.bar_chart(
            chart_data["metric_value"]
        )

        with st.expander(
            "View analytical results"
        ):

            st.dataframe(
                result,
                use_container_width=True,
                hide_index=True,
            )

    except Exception as exc:

        st.warning(
            f"Automatic analysis could not be completed: {exc}"
        )


# =============================================================================
# INTERACTIVE EXPLORATION
# =============================================================================


def _render_explorer(entry: Any):

    dimensions = _entry_dimensions(
        entry
    )

    measures = _entry_measures(
        entry
    )

    if not dimensions or not measures:
        return

    st.markdown(
        "### Explore the Semantic Model"
    )

    left, right = st.columns(2)

    with left:

        selected_dimension = st.selectbox(
            "Dimension",
            dimensions,
            key=(
                "analytics_dimension_"
                + _entry_domain_name(entry)
            ),
            format_func=_pretty_name,
        )

    with right:

        selected_measure = st.selectbox(
            "Measure",
            measures,
            key=(
                "analytics_measure_"
                + _entry_domain_name(entry)
            ),
            format_func=_pretty_name,
        )

    try:

        result = _run_dimension_measure_analysis(
            entry,
            selected_dimension,
            selected_measure,
            limit=25,
        )

        if result.empty:

            st.info(
                "No data returned for this analysis."
            )

            return

        chart_data = result.copy()

        chart_data["dimension_value"] = (
            chart_data[
                "dimension_value"
            ]
            .fillna("Unknown")
            .astype(str)
        )

        chart_data = chart_data.set_index(
            "dimension_value"
        )

        st.bar_chart(
            chart_data["metric_value"]
        )

        st.dataframe(
            result,
            use_container_width=True,
            hide_index=True,
        )

    except Exception as exc:

        st.error(
            f"Unable to execute this analysis: {exc}"
        )


# =============================================================================
# DOMAIN SUMMARY
# =============================================================================


def _render_domain_information(entry: Any):

    domain_name = _entry_domain_name(
        entry
    )

    metric_view = _entry_metric_view(
        entry
    )

    fact_tables = _entry_get(entry, "fact_tables", None) or [_entry_get(entry, "fact_table", "—")]

    row_count = _entry_get(
        entry,
        "row_count",
        None,
    )

    dimensions = _entry_dimensions(
        entry
    )

    measures = _entry_measures(
        entry
    )

    st.markdown(
        "### Governed Semantic Model"
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:

        st.metric(
            "Domain",
            domain_name,
        )

    with c2:

        st.metric(
            "Fact Tables",
            len(fact_tables),
        )

    with c3:

        st.metric(
            "Dimensions",
            len(dimensions),
        )

    with c4:

        if row_count is None:

            display_rows = "—"

        else:

            display_rows = f"{int(row_count):,}"

        st.metric(
            "Source Rows",
            display_rows,
        )

    st.caption(
        f"Metric View: `{metric_view}`"
    )


# =============================================================================
# MAIN PUBLIC FUNCTION
# =============================================================================


def render_domain_dashboard(
    domain: Any,
):
    """
    Main entry point used by pages/5_Analytics.py.

    IMPORTANT:

    `domain` can be either:

        "Healthcare"

    OR:

        RegistryEntry(...)

    OR:

        {"domain_name": "Healthcare", ...}

    This is the specific bug fixed from the previous implementation.
    """

    # -------------------------------------------------------------------------
    # Resolve the RegistryEntry.
    # -------------------------------------------------------------------------

    entry = _resolve_domain_entry(
        domain
    )

    if entry is None:

        if isinstance(
            domain,
            str,
        ):

            domain_label = domain

        else:

            domain_label = _entry_domain_name(
                domain
            )

        st.error(
            f"Domain '{domain_label}' "
            "is not present in the semantic registry."
        )

        return

    # -------------------------------------------------------------------------
    # Validate the Metric View.
    # -------------------------------------------------------------------------

    try:

        metric_view = _entry_metric_view(
            entry
        )

        if not metric_view:

            raise ValueError(
                "Registry entry does not contain "
                "a Metric View."
            )

    except Exception as exc:

        st.error(
            f"Invalid semantic registry entry: {exc}"
        )

        return

    # -------------------------------------------------------------------------
    # Header.
    # -------------------------------------------------------------------------

    domain_name = _entry_domain_name(
        entry
    )

    st.markdown(
        f"## {domain_name} Analytics"
    )

    st.caption(
        "Metadata-driven analytics generated "
        "from the governed semantic model."
    )

    # -------------------------------------------------------------------------
    # Governed model information.
    # -------------------------------------------------------------------------

    _render_domain_information(
        entry
    )

    st.divider()

    # -------------------------------------------------------------------------
    # KPI cards.
    # -------------------------------------------------------------------------

    _render_kpis(
        entry
    )

    st.divider()

    # -------------------------------------------------------------------------
    # Automatic business analysis.
    # -------------------------------------------------------------------------

    _render_default_analysis(
        entry
    )

    st.divider()

    # -------------------------------------------------------------------------
    # Interactive exploration.
    # -------------------------------------------------------------------------

    _render_explorer(
        entry
    )

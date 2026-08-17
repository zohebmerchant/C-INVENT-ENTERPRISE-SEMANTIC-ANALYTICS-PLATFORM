import json
import re

import pandas as pd
import streamlit as st

from theme import (
    navigate_to,
    inject_base_css,
    render_sidebar_brand,
    page_header,
)

import security_fabric as security

from registry import list_domains

from ai_provider import (
    chat,
    is_available,
    provider_name,
)

from publish_engine import (
    get_sql_connection,
)


# =============================================================================
# PAGE SETUP
# =============================================================================

inject_base_css()
render_sidebar_brand()

page_header(
    "Ask AI",
    "Natural-language analytics grounded in the published semantic model",
)


# =============================================================================
# SECURITY / PLATFORM CONFIGURATION
# =============================================================================

if not security.is_configured():

    st.warning(
        "Databricks is not configured for this deployment."
    )

    st.stop()


# =============================================================================
# LOAD PUBLISHED DOMAINS
# =============================================================================

domains = list_domains()

if not domains:

    st.info(
        "No published domains yet — publish a semantic model first."
    )

    if st.button("← Go to Data Onboarding"):

        navigate_to("Data Onboarding")

    st.stop()


domain_names = [
    d.domain_name
    for d in domains
]


active_name = st.selectbox(
    "Ask about",
    domain_names,
    key="ask_ai_domain_selector",
)


entry = next(
    (
        d
        for d in domains
        if d.domain_name == active_name
    ),
    None,
)


if entry is None:

    st.error(
        f"Published semantic model for "
        f"{active_name} could not be found."
    )

    st.stop()


# =============================================================================
# SEMANTIC SOURCE
# =============================================================================

st.caption(
    f"AI provider: **{provider_name()}** · "
    f"Semantic source: `{entry.metric_view}` · "
    f"Fact tables: **{len(getattr(entry, 'fact_tables', []) or [entry.fact_table])}**"
)


# =============================================================================
# AI CONFIGURATION
# =============================================================================

if not is_available():

    st.info(
        "Ask AI needs an approved enterprise LLM endpoint. "
        "Configure the Capgemini enterprise LLM endpoint "
        "in Streamlit Secrets. Analytics and semantic "
        "publishing do not require an LLM."
    )

    st.stop()


# =============================================================================
# IDENTIFIER VALIDATION
# =============================================================================

def _identifier(
    value: str,
) -> str:

    if not re.fullmatch(
        r"[A-Za-z0-9_.$]+",
        value or "",
    ):

        raise ValueError(
            "Unsafe identifier in semantic metadata."
        )

    return value


# =============================================================================
# SEMANTIC MODEL CONTEXT
# =============================================================================

def _build_context() -> str:

    measures = (
        ", ".join(
            entry.measures
            or []
        )
        or "No measures declared"
    )

    dimensions = (
        ", ".join(
            entry.dimensions
            or []
        )
        or "No dimensions declared"
    )

    return f"""
DOMAIN:
{entry.domain_name}

GOVERNED METRIC VIEW:
{_identifier(entry.metric_view)}

FACT TABLES:
{len(getattr(entry, "fact_tables", []) or [entry.fact_table])} (governed Delta tables)

MEASURES:
{measures}

DIMENSIONS:
{dimensions}

IMPORTANT:
The Metric View is the ONLY permitted analytical source.

Do not invent:
- tables
- columns
- joins
- measures
- dimensions
- business definitions
"""


# =============================================================================
# ROBUST JSON PARSER
# =============================================================================

def _parse_llm_json(
    raw: str,
) -> dict:

    """
    Parse JSON returned by the enterprise LLM.

    Handles:

    1. Normal JSON
    2. Markdown ```json blocks
    3. JSON surrounded by explanatory text
    4. Empty responses
    5. Nested JSON object extraction

    Does not silently fabricate a response.
    """

    if raw is None:

        raise RuntimeError(
            "The Capgemini LLM returned no response."
        )

    text = str(
        raw
    ).strip()

    if not text:

        raise RuntimeError(
            "The Capgemini LLM returned an empty response."
        )


    # -------------------------------------------------------------------------
    # Remove Markdown fences
    # -------------------------------------------------------------------------

    text = re.sub(
        r"^```(?:json)?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\s*```$",
        "",
        text,
    )

    text = text.strip()


    # -------------------------------------------------------------------------
    # Attempt 1: response itself is JSON
    # -------------------------------------------------------------------------

    try:

        parsed = json.loads(
            text
        )

        if isinstance(
            parsed,
            dict,
        ):

            return parsed

    except json.JSONDecodeError:

        pass


    # -------------------------------------------------------------------------
    # Attempt 2: locate JSON object inside text
    # -------------------------------------------------------------------------

    start = text.find(
        "{"
    )

    if start >= 0:

        depth = 0
        in_string = False
        escaped = False

        for index in range(
            start,
            len(text),
        ):

            char = text[index]


            if escaped:

                escaped = False
                continue


            if char == "\\" and in_string:

                escaped = True
                continue


            if char == '"':

                in_string = not in_string
                continue


            if in_string:

                continue


            if char == "{":

                depth += 1


            elif char == "}":

                depth -= 1

                if depth == 0:

                    candidate = text[
                        start:index + 1
                    ]

                    try:

                        parsed = json.loads(
                            candidate
                        )

                        if isinstance(
                            parsed,
                            dict,
                        ):

                            return parsed

                    except json.JSONDecodeError:

                        pass

                    break


    # -------------------------------------------------------------------------
    # Attempt 3: find a SQL object manually
    #
    # This is a fallback in case the model returned something like:
    #
    # Here is the query:
    # {"sql":"SELECT ..."}
    #
    # but malformed surrounding content.
    # -------------------------------------------------------------------------

    sql_match = re.search(
        r'"sql"\s*:\s*"((?:\\.|[^"\\])*)"',
        text,
        flags=re.IGNORECASE,
    )

    if sql_match:

        try:

            sql_value = json.loads(
                '"' + sql_match.group(1) + '"'
            )

        except json.JSONDecodeError:

            sql_value = sql_match.group(1)


        explanation_match = re.search(
            r'"explanation"\s*:\s*"((?:\\.|[^"\\])*)"',
            text,
            flags=re.IGNORECASE,
        )

        explanation = ""

        if explanation_match:

            try:

                explanation = json.loads(
                    '"'
                    + explanation_match.group(1)
                    + '"'
                )

            except json.JSONDecodeError:

                explanation = (
                    explanation_match.group(1)
                )


        return {
            "sql": sql_value,
            "explanation": explanation,
        }


    # -------------------------------------------------------------------------
    # Nothing worked
    # -------------------------------------------------------------------------

    raise RuntimeError(
        "The enterprise LLM returned text that was "
        "not valid JSON for SQL planning.\n\n"
        "LLM response:\n"
        f"{text[:4000]}"
    )


# =============================================================================
# SQL GENERATION
# =============================================================================

def _generate_sql(
    question: str,
) -> tuple[str, str]:

    metric_view = _identifier(
        entry.metric_view
    )


    system = f"""
You are the SQL planner for an enterprise
semantic analytics platform.

{_build_context()}

Generate exactly ONE read-only Databricks SQL
query for the user's question.

STRICT GOVERNANCE RULES:

1. Use ONLY this governed Metric View:

   {metric_view}

2. Never query raw source tables.

3. Never query another domain.

4. Never query information_schema.

5. Never query system tables.

6. Never invent columns.

7. Never invent measures.

8. Never invent dimensions.

9. Use only measures declared by the
   semantic model.

10. Use only dimensions declared by the
    semantic model.

11. Do not create joins.

12. Do not reference any table other than
    the governed Metric View.

13. The generated SQL must reference:

    {metric_view}

14. Only read-only SQL is allowed.

15. Never generate:

    INSERT
    UPDATE
    DELETE
    MERGE
    DROP
    ALTER
    CREATE
    COPY
    GRANT
    REVOKE
    CALL
    SET
    USE
    TRUNCATE

16. Never generate multiple SQL statements.

17. If the question cannot be answered from
    the semantic model, do not invent an answer.

18. Every declared Metric View measure MUST be evaluated
    with the Databricks MEASURE() function.

    CORRECT:
    SELECT MEASURE(avg_heart_rate)
    FROM <governed_metric_view>

    CORRECT:
    SELECT doctors_doctor_name,
           MEASURE(avg_heart_rate) AS avg_heart_rate
    FROM <governed_metric_view>
    GROUP BY ALL

    WRONG:
    SELECT avg_heart_rate
    FROM <governed_metric_view>

    WRONG:
    SELECT AVG(avg_heart_rate)
    FROM <governed_metric_view>

    WRONG:
    SELECT SUM(avg_heart_rate)
    FROM <governed_metric_view>

19. Do not wrap a Metric View measure in
    AVG(), SUM(), COUNT(), MIN(), or MAX().
    The Metric View measure definition already owns
    its aggregation semantics.

20. If a measure is selected, reference it as:
    MEASURE(<measure_name>)

21. If dimensions and measures are selected together,
    use GROUP BY ALL unless the query is otherwise
    invalid for Databricks.

22. Return ONLY valid JSON.

23. Do NOT use Markdown code fences.

24. Do NOT put text before or after the JSON.

Required response:

{{
  "sql": "SELECT ...",
  "explanation": "short explanation"
}}
"""


    try:

        result = chat(
            [
                {
                    "role": "system",
                    "content": system,
                },
                {
                    "role": "user",
                    "content": question,
                },
            ],
            temperature=0.0,
            max_tokens=1200,
        )

    except Exception as exc:

        raise RuntimeError(
            f"Enterprise LLM request failed: {exc}"
        ) from exc


    if result is None:

        raise RuntimeError(
            "The enterprise LLM returned no result."
        )


    raw = str(
        result.text
        or ""
    ).strip()


    if not raw:

        raise RuntimeError(
            "The enterprise LLM returned an empty response."
        )


    # -------------------------------------------------------------------------
    # Parse robustly
    # -------------------------------------------------------------------------

    obj = _parse_llm_json(
        raw
    )


    # -------------------------------------------------------------------------
    # Extract SQL
    # -------------------------------------------------------------------------

    sql = str(
        obj.get(
            "sql",
            "",
        )
    ).strip()


    explanation = str(
        obj.get(
            "explanation",
            "",
        )
    ).strip()


    if not sql:

        raise RuntimeError(
            "The enterprise LLM returned JSON, "
            "but no SQL query was provided.\n\n"
            f"LLM response:\n{raw[:4000]}"
        )


    return (
        sql,
        explanation,
    )


# =============================================================================
# SQL GOVERNANCE VALIDATION
# =============================================================================

def _validate_sql(
    sql: str,
):

    if not sql:

        raise ValueError(
            "Generated SQL is empty."
        )


    compact = re.sub(
        r"\s+",
        " ",
        sql.strip(),
    )


    upper = compact.upper()


    # -------------------------------------------------------------------------
    # Only SELECT / WITH
    # -------------------------------------------------------------------------

    if not (
        upper.startswith("SELECT ")
        or upper.startswith("WITH ")
    ):

        raise ValueError(
            "The AI generated a non-read-only query."
        )


    # -------------------------------------------------------------------------
    # No multiple statements
    # -------------------------------------------------------------------------

    if ";" in compact.rstrip(";"):

        raise ValueError(
            "Multiple SQL statements are not allowed."
        )


    # -------------------------------------------------------------------------
    # Forbidden SQL operations
    # -------------------------------------------------------------------------

    forbidden = [
        " INSERT ",
        " UPDATE ",
        " DELETE ",
        " MERGE ",
        " DROP ",
        " ALTER ",
        " CREATE ",
        " COPY ",
        " GRANT ",
        " REVOKE ",
        " CALL ",
        " SET ",
        " USE ",
        " TRUNCATE ",
    ]


    padded = (
        " "
        + upper
        + " "
    )


    for token in forbidden:

        if token in padded:

            raise ValueError(
                "The generated SQL contains "
                f"a forbidden operation: {token.strip()}"
            )


    # -------------------------------------------------------------------------
    # Must use governed Metric View
    # -------------------------------------------------------------------------

    governed_view = (
        _identifier(
            entry.metric_view
        )
    )


    if governed_view.lower() not in sql.lower():

        raise ValueError(
            "The generated SQL did not use "
            "the governed Metric View."
        )


    # -------------------------------------------------------------------------
    # Metric View measure validation
    # -------------------------------------------------------------------------
    #
    # Databricks Metric Views require measure evaluations
    # to use MEASURE(<measure_name>). This is enforced
    # deterministically rather than relying only on the LLM.
    # -------------------------------------------------------------------------

    declared_measures = [
        str(measure).strip()
        for measure in (entry.measures or [])
        if str(measure).strip()
    ]

    for measure in declared_measures:

        bare_measure_pattern = re.compile(
            rf"(?<![A-Za-z0-9_]){re.escape(measure)}(?![A-Za-z0-9_])",
            flags=re.IGNORECASE,
        )

        if not bare_measure_pattern.search(sql):
            continue

        measure_function_pattern = re.compile(
            rf"\bMEASURE\s*\(\s*{re.escape(measure)}\s*\)",
            flags=re.IGNORECASE,
        )

        if not measure_function_pattern.search(sql):
            raise ValueError(
                f"Metric View measure '{measure}' must be "
                "evaluated with MEASURE(). "
                f"Use MEASURE({measure}) instead of referencing "
                f"{measure} directly or wrapping it in another "
                "aggregation function."
            )

        reaggregation_pattern = re.compile(
            rf"\b(?:AVG|SUM|COUNT|MIN|MAX)\s*\(\s*"
            rf"(?:MEASURE\s*\(\s*)?"
            rf"{re.escape(measure)}"
            rf"\s*\)?\s*\)",
            flags=re.IGNORECASE,
        )

        if reaggregation_pattern.search(sql):
            raise ValueError(
                f"Metric View measure '{measure}' must not be "
                "re-aggregated with AVG/SUM/COUNT/MIN/MAX."
            )


    # -------------------------------------------------------------------------
    # Prevent unexpectedly large SQL
    # -------------------------------------------------------------------------

    if len(sql) > 12000:

        raise ValueError(
            "Generated SQL is unexpectedly large."
        )


# =============================================================================
# EXECUTE GOVERNED SQL
# =============================================================================

def _execute(
    sql: str,
) -> pd.DataFrame:

    # Always validate again immediately before execution.
    _validate_sql(
        sql
    )


    with get_sql_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                sql
            )

            rows = (
                cur.fetchall()
            )

            columns = [
                c[0]
                for c in (
                    cur.description
                    or []
                )
            ]


    return pd.DataFrame(
        rows,
        columns=columns,
    )


# =============================================================================
# BUSINESS EXPLANATION
# =============================================================================

def _explain(
    question: str,
    sql: str,
    result: pd.DataFrame,
) -> str:

    preview = (
        result
        .head(20)
        .to_dict(
            orient="records"
        )
    )


    semantic_source = (
        entry.metric_view
    )


    system_prompt = f"""
You are an enterprise analytics assistant.

Domain:
{entry.domain_name}

Governed semantic source:
{semantic_source}

Your job is to explain the result of a
governed analytics query.

Rules:

1. Use only information present in the result.

2. Do not invent facts.

3. Do not invent numbers.

4. Do not introduce information from other domains.

5. Keep the answer concise and business-friendly.

6. Mention the governed semantic source when useful.

7. If the result is empty, clearly state that
   no matching records were returned.

8. Do not generate SQL.
"""


    try:

        response = chat(
            [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": (
                        f"User question:\n"
                        f"{question}\n\n"

                        f"Generated SQL:\n"
                        f"{sql}\n\n"

                        f"Query result:\n"
                        f"{preview}"
                    ),
                },
            ],
            temperature=0.1,
            max_tokens=900,
        )

    except Exception as exc:

        # The SQL has already executed successfully.
        # Therefore, don't fail the entire answer simply
        # because the optional explanation call failed.

        return (
            f"The query completed successfully, but "
            f"the AI explanation could not be generated.\n\n"
            f"Semantic source: `{semantic_source}`\n\n"
            f"Explanation service error: {exc}"
        )


    text = str(
        response.text
        if response
        else ""
    ).strip()


    if not text:

        return (
            "The query completed successfully.\n\n"
            f"Semantic source: `{semantic_source}`"
        )


    return text


# =============================================================================
# SESSION STATE
# =============================================================================

if (
    "ask_ai_messages"
    not in st.session_state
):

    st.session_state.ask_ai_messages = {}


messages = (
    st.session_state
    .ask_ai_messages
    .setdefault(
        active_name,
        [],
    )
)


# =============================================================================
# DISPLAY CHAT HISTORY
# =============================================================================

for msg in messages:

    with st.chat_message(
        msg["role"]
    ):

        st.markdown(
            msg["content"]
        )


        if msg.get(
            "source"
        ):

            st.caption(
                msg["source"]
            )


        if msg.get(
            "sql"
        ):

            with st.expander(
                "Show generated SQL"
            ):

                st.code(
                    msg["sql"],
                    language="sql",
                )


        if msg.get(
            "data"
        ) is not None:

            st.dataframe(
                msg["data"],
                use_container_width=True,
                hide_index=True,
            )


# =============================================================================
# EXAMPLES
# =============================================================================

if not messages:

    first_measure = (
        entry.measures[0]
        if entry.measures
        else "metrics"
    )

    first_dimension = (
        entry.dimensions[0]
        if entry.dimensions
        else "categories"
    )


    examples = [
        f"What are the main {first_measure}?",
        (
            f"Show the top {first_dimension} "
            f"by {first_measure}."
        ),
        "Give me the key business insight from this domain.",
    ]


    st.info(
        "Try one of these:\n\n"
        + "\n".join(
            f"- {x}"
            for x in examples
        )
    )


# =============================================================================
# CHAT INPUT
# =============================================================================

question = st.chat_input(
    f"Ask anything about {active_name}…"
)


# =============================================================================
# PROCESS QUESTION
# =============================================================================

if question:

    question = question.strip()


    if not question:

        st.stop()


    messages.append(
        {
            "role": "user",
            "content": question,
        }
    )


    with st.chat_message(
        "assistant"
    ):

        try:

            # -----------------------------------------------------------------
            # 1. Generate SQL
            # -----------------------------------------------------------------

            with st.spinner(
                "Understanding the semantic model..."
            ):

                sql, planning_note = (
                    _generate_sql(
                        question
                    )
                )


            # -----------------------------------------------------------------
            # 2. Validate SQL
            # -----------------------------------------------------------------

            with st.spinner(
                "Validating governed SQL..."
            ):

                _validate_sql(
                    sql
                )


            # -----------------------------------------------------------------
            # 3. Execute Databricks query
            # -----------------------------------------------------------------

            with st.spinner(
                "Querying the governed Metric View..."
            ):

                data = _execute(
                    sql
                )


            # -----------------------------------------------------------------
            # 4. Explain result
            # -----------------------------------------------------------------

            with st.spinner(
                "Preparing the business explanation..."
            ):

                answer = _explain(
                    question,
                    sql,
                    data,
                )


            # -----------------------------------------------------------------
            # 5. Display answer
            # -----------------------------------------------------------------

            st.markdown(
                answer
            )


            if planning_note:

                st.caption(
                    planning_note
                )


            st.caption(
                f"Semantic source: "
                f"`{entry.metric_view}`"
            )


            # -----------------------------------------------------------------
            # 6. Display data
            # -----------------------------------------------------------------

            if not data.empty:

                st.dataframe(
                    data,
                    use_container_width=True,
                    hide_index=True,
                )

            else:

                st.info(
                    "The query completed successfully "
                    "but returned no matching records."
                )


            # -----------------------------------------------------------------
            # 7. SQL
            # -----------------------------------------------------------------

            with st.expander(
                "Show generated SQL"
            ):

                st.code(
                    sql,
                    language="sql",
                )


            # -----------------------------------------------------------------
            # 8. Save assistant response
            # -----------------------------------------------------------------

            messages.append(
                {
                    "role": "assistant",
                    "content": answer,
                    "source": (
                        f"Semantic source: "
                        f"{entry.metric_view}"
                    ),
                    "sql": sql,
                    "data": data,
                }
            )


        except Exception as exc:

            error = (
                "I could not safely answer that "
                "question from the governed semantic model:\n\n"
                f"{exc}"
            )


            st.error(
                error
            )


            messages.append(
                {
                    "role": "assistant",
                    "content": error,
                }
            )

"""
Enterprise Semantic Analytics Platform — AI-Assisted Layer.

Calls a Databricks Foundation Model API endpoint (direct REST, same
pattern as security_fabric's Genie calls — no `openai` package
dependency) to catch relationships the deterministic heuristic in
semantic_engine.py can't find by name-matching alone, and to draft
richer, human-readable glossary definitions than the mechanical
fallback.

Every output here is a SUGGESTION. Nothing from this module is ever
merged into a SemanticModel without being shown to a human first — see
app.py's review step. This is the concrete implementation of "AI
proposes -> system validates -> controlled publish."
"""

from __future__ import annotations

import json
import re

import streamlit as st

from semantic_engine import RelationshipCandidate, GlossaryEntry
import security_fabric as security

FOUNDATION_MODEL_ENDPOINT = "databricks-meta-llama-3-3-70b-instruct"
# Representative Databricks Foundation Model APIs endpoint name — confirm
# the exact endpoint available in your workspace's Serving tab before a
# live demo; names vary by workspace/region and change over time.


def _query_foundation_model(prompt: str, max_tokens: int = 900) -> str:
    import requests

    w = security.get_workspace_client()
    host = st.secrets["DATABRICKS_HOST"].rstrip("/")
    headers = w.config.authenticate()

    url = f"{host}/serving-endpoints/{FOUNDATION_MODEL_ENDPOINT}/invocations"
    body = {"messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens, "temperature": 0.1}
    resp = requests.post(url, headers={**headers, "Content-Type": "application/json"}, json=body, timeout=60)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def suggest_fuzzy_relationships(profiles: dict, already_found: list) -> list:
    """AI proposes relationships the name-matching heuristic missed
    (e.g. cust_id vs customer_id). Runs only on columns NOT already
    matched — never overrides or second-guesses a heuristic match."""
    if not security.is_configured():
        return []

    already_matched = {(r.from_table, r.from_column) for r in already_found}
    column_summary = []
    for table_name, profile in profiles.items():
        for col in profile.columns:
            if (table_name, col.name) in already_matched:
                continue
            column_summary.append({
                "table": table_name, "column": col.name, "dtype": col.dtype,
                "sample_values": [str(v) for v in col.sample_values[:3]],
            })

    if len(column_summary) < 2:
        return []

    prompt = f"""You identify likely join relationships between database columns from
DIFFERENT tables that a name-matching algorithm already checked and could NOT match by
name alone. Propose pairs that likely represent the same real-world entity, based on
naming similarity, data type, and sample values. Only propose pairs you're reasonably
confident about — a human reviews these.

Columns:
{json.dumps(column_summary, indent=2)}

Respond with ONLY a JSON array, no other text:
[{{"table_a": "...", "column_a": "...", "table_b": "...", "column_b": "...", "confidence": 0.0-1.0, "reason": "one sentence"}}]
If none, respond with: []
"""
    try:
        raw = _query_foundation_model(prompt)
        raw = re.sub(r'^```(json)?|```$', '', raw.strip(), flags=re.MULTILINE).strip()
        suggestions = json.loads(raw)
    except Exception as e:
        st.warning(f"AI relationship suggestions unavailable this run: {e}")
        return []

    candidates = []

    valid_tables = set(profiles)

    for s in suggestions:

        try:
            table_a = s["table_a"]
            column_a = s["column_a"]
            table_b = s["table_b"]
            column_b = s["column_b"]
            confidence = float(
                s.get("confidence", 0.5)
            )

            if table_a not in valid_tables:
                continue

            if table_b not in valid_tables:
                continue

            if table_a == table_b:
                # Fuzzy relationship suggestions are for cross-table
                # matching only. Same-table hierarchies are handled by
                # semantic_engine.detect_self_referencing_relationships().
                continue

            profile_a = profiles[table_a]
            profile_b = profiles[table_b]

            columns_a = {
                c.name: c
                for c in profile_a.columns
            }

            columns_b = {
                c.name: c
                for c in profile_b.columns
            }

            if column_a not in columns_a:
                continue

            if column_b not in columns_b:
                continue

            # AI must not suggest a numeric metric column as a key.
            if (
                not _looks_like_id_for_ai(
                    column_a
                )
                and not _looks_like_id_for_ai(
                    column_b
                )
            ):
                # Keep non-ID fuzzy keys only if the names strongly
                # indicate an identifier/business key.
                normalized_a = re.sub(
                    r"[^a-z0-9]",
                    "",
                    column_a.lower(),
                )
                normalized_b = re.sub(
                    r"[^a-z0-9]",
                    "",
                    column_b.lower(),
                )

                key_tokens = (
                    "id",
                    "key",
                    "code",
                    "number",
                    "no",
                )

                if not any(
                    token in normalized_a
                    for token in key_tokens
                ) or not any(
                    token in normalized_b
                    for token in key_tokens
                ):
                    continue

            candidates.append(
                RelationshipCandidate(
                    from_table=table_a,
                    from_column=column_a,
                    to_table=table_b,
                    to_column=column_b,
                    confidence=max(
                        0.0,
                        min(
                            1.0,
                            confidence,
                        ),
                    ),
                    reason=(
                        "AI suggestion: "
                        f"{s.get('reason', 'similar column semantics')}"
                    ),
                    is_ai_suggested=True,
                )
            )

        except (
            KeyError,
            ValueError,
            TypeError,
        ):
            continue

    return candidates


def _looks_like_id_for_ai(
    column_name: str,
) -> bool:
    """
    Conservative AI-side identifier test.

    AI suggestions must not turn ordinary descriptive columns such as
    product_name or store_name into relationships.
    """
    normalized = re.sub(
        r"[^a-z0-9]",
        "",
        column_name.lower(),
    )

    return (
        normalized == "id"
        or normalized.endswith("id")
        or "key" in normalized
        or "code" in normalized
        or normalized.endswith("number")
        or normalized.endswith("no")
    )


def draft_glossary_entries(profiles: dict, domain_name: str) -> list:
    """AI drafts richer, business-friendly glossary definitions than the
    mechanical rule-based fallback in semantic_engine.generate_glossary().
    Both paths produce the same GlossaryEntry shape — a human reviews
    either before it's treated as final."""
    if not security.is_configured():
        return []

    columns = []
    for table_name, profile in profiles.items():
        for col in profile.columns:
            columns.append({"table": table_name, "column": col.name, "dtype": col.dtype})

    if not columns:
        return []

    prompt = f"""You are drafting a business glossary for a {domain_name} dataset. For each
column below, write ONE short, business-friendly definition (not a technical description) —
the kind a non-technical business user would find useful.

Columns:
{json.dumps(columns, indent=2)}

Respond with ONLY a JSON array, no other text:
[{{"table": "...", "column": "...", "definition": "..."}}]
"""
    try:
        raw = _query_foundation_model(prompt, max_tokens=1500)
        raw = re.sub(r'^```(json)?|```$', '', raw.strip(), flags=re.MULTILINE).strip()
        drafts = json.loads(raw)
    except Exception as e:
        st.warning(f"AI glossary drafting unavailable this run: {e}")
        return []

    entries = []
    for d in drafts:
        try:
            entries.append(GlossaryEntry(
                term=d["column"].replace("_", " ").title(),
                definition=d["definition"],
                source_column=f"{d['table']}.{d['column']}",
            ))
        except (KeyError, TypeError):
            continue
    return entries

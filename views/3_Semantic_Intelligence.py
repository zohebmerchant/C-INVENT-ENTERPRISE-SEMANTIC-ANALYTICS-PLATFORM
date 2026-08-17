import pandas as pd
import streamlit as st

from theme import navigate_to, inject_base_css, render_sidebar_brand, page_header, section_title

inject_base_css()
render_sidebar_brand()

page_header("Semantic Intelligence", "What the AI found — every relationship, fact, dimension, and warning")

model = st.session_state.get("model")
if not model:
    st.warning("No semantic model yet.")
    if st.button("← Go to Data Onboarding"):
        navigate_to("Data Onboarding")
    st.stop()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Tables Analyzed", len(model.tables))
c2.metric("Relationships Found", len(model.relationships))
c3.metric("Fact Tables", len(model.facts))
c4.metric("Dimension Tables", len(model.dimensions))

if model.warnings:
    with st.container(border=True):
        section_title("Warnings", "Review these before publishing")
        for w in model.warnings:
            st.markdown(f"- {w}")

if model.pii_findings:
    st.markdown(
        '<div class="platform-banner warn">PII / PHI detected in the columns below. '
        "See the Security Center for masking recommendations before wider access is granted.</div>",
        unsafe_allow_html=True,
    )

tab1, tab2, tab3, tab4 = st.tabs(["Tables", "Relationships", "Metrics", "Glossary"])

with tab1:
    for name, profile in model.tables.items():
        with st.container(border=True):
            tag = "fact" if name in model.facts else "dim"
            tag_label = "FACT" if name in model.facts else "DIMENSION"
            pii_cols = model.pii_findings.get(name, [])
            pii_badge = ' <span class="platform-tag pii">PII/PHI</span>' if pii_cols else ""
            st.markdown(
                f'<div class="platform-card-title">{name} <span class="platform-tag {tag}">{tag_label}</span>{pii_badge}</div>'
                f'<div class="platform-card-sub">{profile.row_count:,} rows · {len(profile.columns)} columns'
                f'{" · duplicates: " + str(profile.duplicate_row_count) if profile.duplicate_row_count else ""}</div>',
                unsafe_allow_html=True,
            )
            if profile.quality_warnings:
                for qw in profile.quality_warnings:
                    st.caption(f"⚠ {qw}")
            col_df = pd.DataFrame([{
                "Column": c.name, "Type": c.dtype, "Null %": c.null_pct,
                "Distinct": c.distinct_count, "Uniqueness": f"{c.uniqueness_ratio*100:.0f}%",
                "PII": c.pii_category or "",
            } for c in profile.columns])
            st.dataframe(col_df, use_container_width=True, hide_index=True)

with tab2:

    if not model.relationships:

        st.info(
            "No relationships detected. "
            "Try uploading files that share a common key column."
        )

    for rel in model.relationships:

        conf_class = (
            "ok"
            if rel.confidence >= 0.8
            else (
                "dim"
                if rel.confidence >= 0.6
                else "pii"
            )
        )

        ai_badge = (
            ' <span class="platform-tag ai">AI SUGGESTED</span>'
            if rel.is_ai_suggested
            else ""
        )

        m2m_badge = (
            ' <span class="platform-tag pii">MANY-TO-MANY</span>'
            if rel.is_many_to_many
            else ""
        )

        with st.container(border=True):

            st.markdown(
                f"""
                <div class="platform-card-title">
                    {rel.from_table}.{rel.from_column}
                    →
                    {rel.to_table}.{rel.to_column}
                    <span class="platform-tag {conf_class}">
                        {rel.confidence * 100:.0f}% confidence
                    </span>
                    {ai_badge}
                    {m2m_badge}
                </div>
                <div class="platform-card-sub">
                    {rel.reason}
                </div>
                """,
                unsafe_allow_html=True,
            )

            if (
                not rel.is_ai_suggested
                and "AI independently supported" in rel.reason
            ):
                st.caption(
                    "✓ Deterministic relationship retained; "
                    "AI independently corroborated the same edge. "
                    "Reverse AI suggestions are not duplicated."
                )

    st.caption(
        "Relationship direction is canonical FK → PK. "
        "The same relationship cannot appear twice simply because "
        "an AI suggestion used the reverse direction."
    )


    if model.ai_suggestions:
        st.divider()
        section_title(
            "AI Relationship Suggestions",
            "Potential relationships detected by AI — review before publishing",
        )

        for rel in model.ai_suggestions:
            with st.container(border=True):
                st.markdown(
                    f"""
                    **{rel.from_table}.{rel.from_column}**
                    →
                    **{rel.to_table}.{rel.to_column}**

                    **{rel.confidence * 100:.0f}% confidence · AI SUGGESTED**
                    """
                )
                st.caption(rel.reason)

        st.caption(
            "AI suggestions are intentionally excluded from the governed "
            "graph until independently validated. Publishing uses only "
            "deterministic, validated relationships."
        )

with tab3:
    if not model.metrics:
        st.info("No metrics generated yet — no fact table was confidently identified.")
    for m in model.metrics:
        with st.container(border=True):
            st.markdown(f'<div class="platform-card-title">{m.name}</div>', unsafe_allow_html=True)
            st.code(m.expression, language="sql")
            st.caption(m.description)

with tab4:
    if model.glossary:
        gdf = pd.DataFrame([{"Term": g.term, "Definition": g.definition, "Source": g.source_column} for g in model.glossary])
        st.dataframe(gdf, use_container_width=True, hide_index=True)
    else:
        st.info("No glossary entries generated.")

st.divider()
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("✓ QA Validation →", use_container_width=True):
        navigate_to("QA Validation")
with col2:
    if st.button("View Business Model →", use_container_width=True):
        navigate_to("Business Model")
with col3:
    if st.button("Publish & View Analytics →", use_container_width=True, type="primary"):
        navigate_to("Business Model")

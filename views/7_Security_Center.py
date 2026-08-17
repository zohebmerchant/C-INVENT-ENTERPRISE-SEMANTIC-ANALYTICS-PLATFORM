import streamlit as st

from theme import inject_base_css, render_sidebar_brand, page_header, section_title
import security_fabric as security
from registry import list_domains

inject_base_css()
render_sidebar_brand()

page_header("Security Center", "What's automatic, what was reviewed, and what still needs a human")

if not security.is_configured():
    st.markdown(
        '<div class="platform-banner warn">Databricks is not configured for this deployment.</div>',
        unsafe_allow_html=True,
    )
    st.stop()

col1, col2 = st.columns(2)

with col1:
    with st.container(border=True):
        section_title("Fully Automatic", "No manual Databricks step, per domain published")
        automatic = [
            "Relationship detection", "Fact / dimension detection", "Data quality checks",
            "PII / PHI column detection", "Metric View generation",
            "Schema and table creation for each new domain",
            "Genie space registration for new Metric Views (if configured)",
        ]
        for a in automatic:
            st.markdown(f"✅ {a}")

with col2:
    with st.container(border=True):
        section_title("Requires Human Approval", "AI proposes → system validates → controlled publish")
        human = [
            "One-time platform bootstrap (see databricks_bootstrap.py — creates the dedicated catalog once, not per domain)",
            "Applying PII/PHI masking (flagged automatically, applied on review)",
            "Certifying a model as trusted for enterprise reporting",
            "Granting access to a separate reader identity, if one is configured",
        ]
        for h in human:
            st.markdown(f"⚠️ {h}")

st.divider()

with st.container(border=True):
    section_title("Recent Security Actions", "The actual audit trail from the last publish, if any")
    actions = st.session_state.get("security_actions", [])
    if not actions:
        st.info("No publish has run in this session yet — publish a domain to see real security actions here.")
    else:
        for a in actions:
            icon = "✅" if a.status == "success" else "⚠️"
            st.markdown(f"{icon} **{a.action}** on `{a.target}` → `{a.principal}`  \n{a.detail}")

st.divider()

with st.container(border=True):
    section_title("PII / PHI Across Published Domains")
    model = st.session_state.get("model")
    if model and model.pii_findings:
        for table, cols in model.pii_findings.items():
            st.markdown(f"**{table}**: {', '.join(cols)}")
    else:
        st.caption("No PII/PHI findings from the current session's analysis.")

st.divider()
st.caption(
    "This platform authenticates with a workspace Personal Access Token, generated once "
    "and provided to the app via its own secrets — not a separate service principal requiring "
    "manual grants. The dedicated catalog for this platform was created exactly once, by "
    "running databricks_bootstrap.py, not through this UI and not repeated per upload. "
    "Everything above this line, for every domain published after that one-time step, "
    "runs with no manual Databricks intervention."
)

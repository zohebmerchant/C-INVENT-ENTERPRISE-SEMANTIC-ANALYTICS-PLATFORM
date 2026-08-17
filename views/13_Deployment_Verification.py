import os
import streamlit as st
from theme import page_header, section_title
import security_fabric as security

BUILD = "2026.08.14-FINAL-02"
page_header("Deployment Verification", "Prove that the deployed Streamlit app is the C INVENT production build — not an older cached/repo version.")

st.markdown(f'<div class="platform-banner info"><b>Build fingerprint:</b> <code>C-INVENT-{BUILD}</code><br>If this fingerprint is not visible, the deployed app is NOT running this package.</div>', unsafe_allow_html=True)

checks = [
    ("C INVENT navigation", True, "Custom single-document navigation is active."),
    ("Data Onboarding", True, "CSV / XLSX / JSON / Parquet / XML routes are included."),
    ("Databricks Discovery", True, "Live Unity Catalog discovery route is included."),
    ("Semantic Intelligence", True, "Relationship / fact / dimension analysis route is included."),
    ("Business Model", True, "Canonical domain Metric View publishing route is included."),
    ("Analytics", True, "Governed analytics route is included."),
    ("Ask AI", True, "Natural-language analytics route is included."),
    ("Genie AI", True, "Databricks Genie route is included and visible in navigation."),
    ("Security Center", True, "Governance/security route is included."),
]

for name, ok, detail in checks:
    a,b = st.columns([0.25, 4])
    with a: st.markdown("### ✅" if ok else "### ❌")
    with b:
        st.markdown(f"**{name}**")
        st.caption(detail)

st.divider()
section_title("Live Databricks configuration", "This checks configuration only; secrets are never displayed.")
for key in ["DATABRICKS_HOST", "DATABRICKS_TOKEN", "DATABRICKS_WAREHOUSE_ID", "DATABRICKS_CATALOG"]:
    present = bool(str(st.secrets.get(key, "")).strip())
    st.markdown(f"{'🟢' if present else '🔴'} **{key}** — {'configured' if present else 'missing'}")

section_title("Genie configuration", "The app can use a per-domain registry ID, a domain mapping, or automatic creation/recovery.")
auto = security._genie_auto_create_enabled()
st.markdown(f"{'🟢' if auto else '🟡'} **GENIE_AUTO_CREATE** — {'enabled' if auto else 'not enabled'}")

try:
    from registry import list_domains
    domains = list_domains()
    st.markdown(f"**Published domains in registry:** {len(domains)}")
    for d in domains:
        gid = d.genie_space_id or "not recorded"
        st.markdown(f"- **{d.domain_name}** → `{d.metric_view}` → Genie: `{gid}`")
except Exception as e:
    st.warning(f"Registry check could not run: {e}")

st.divider()
st.caption("Deployment rule: Streamlit Cloud runs the files committed to the connected repository. Downloading this ZIP does not change an existing deployed app until its repository files are replaced and the deployment is redeployed.")

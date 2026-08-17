import streamlit as st

from theme import navigate_to, inject_base_css, render_sidebar_brand, page_header
import security_fabric as security
from registry import list_domains
from analytics_engine import render_domain_dashboard

inject_base_css()
render_sidebar_brand()

page_header("Analytics", "Auto-generated from whatever's been published — switch domains, no redeploy")

if not security.is_configured():
    st.markdown(
        '<div class="platform-banner warn">Databricks is not configured for this deployment. '
        "Publish a domain first (see Business Model page) once Databricks secrets are set.</div>",
        unsafe_allow_html=True,
    )
    st.stop()

with st.spinner("Loading published domains from the metadata registry…"):
    domains = list_domains()

if not domains:
    st.info("No domains published yet.")
    if st.button("← Go publish your first domain"):
        navigate_to("Data Onboarding")
    st.stop()

domain_names = [d.domain_name for d in domains]
default_idx = 0
if st.session_state.get("last_published_domain") in domain_names:
    default_idx = domain_names.index(st.session_state["last_published_domain"])

active_name = st.selectbox("Active Domain", domain_names, index=default_idx, key="active_domain_selector")
active_entry = next(d for d in domains if d.domain_name == active_name)

st.caption(
    f"This dashboard is rendered entirely from the metadata registry row for **{active_name}** — "
    f"the same rendering code runs for every domain published on this platform."
)

with st.container(border=True):
    render_domain_dashboard(active_entry)

if len(domains) > 1:
    st.divider()
    st.caption(f"{len(domains)} domains live on this platform: {', '.join(domain_names)} — same application, no code changes between them.")

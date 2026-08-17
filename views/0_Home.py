import streamlit as st

from theme import navigate_to, inject_base_css, render_sidebar_brand, section_title
import security_fabric as security

inject_base_css()
render_sidebar_brand()

st.markdown(
    """
    <div style="background:#0F1F35; border-radius:14px; padding:44px 40px; margin-bottom:24px;">
      <div style="color:#C97D3F; font-size:12.5px; font-weight:700; letter-spacing:2px; margin-bottom:10px;">
        ENTERPRISE SEMANTIC ANALYTICS PLATFORM
      </div>
      <div style="color:#FFFFFF; font-family:Georgia,serif; font-size:32px; font-weight:700; line-height:1.25; margin-bottom:14px;">
        Turn any data into governed,<br>AI-ready analytics — automatically.
      </div>
      <div style="color:#C7D2DC; font-size:15px; max-width:700px;">
        One application. Any domain. Upload data, and AI builds the semantic model,
        the dashboards, and the natural-language analytics — with no developer,
        no notebook, and no per-domain code.
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

col1, col2 = st.columns([1, 1])
with col1:
    if st.button("＋ Connect Data", type="primary", use_container_width=True):
        navigate_to("Data Onboarding")
with col2:
    if st.button("View Analytics", use_container_width=True):
        navigate_to("Analytics")

st.markdown("<br>", unsafe_allow_html=True)

# Explicit onboarding split requested for the final product.
ob1, ob2 = st.columns(2)
with ob1:
    with st.container(border=True):
        st.markdown("### ⇧ Data Onboarding")
        st.caption("CSV · XLSX · JSON · Parquet · XML — profile and onboard source data.")
        if st.button("Open Data Onboarding →", use_container_width=True, key="home_onboard"):
            navigate_to("Data Onboarding")
with ob2:
    with st.container(border=True):
        st.markdown("### ⌘ Databricks Discovery")
        st.caption("Unity Catalog · schemas · tables · columns · real Metric Views.")
        if st.button("Open Databricks Discovery →", use_container_width=True, key="home_discovery"):
            navigate_to("Databricks Discovery")

st.divider()

domains = ["Healthcare", "Finance", "Retail", "Banking", "Insurance", "Manufacturing", "Any Domain"]
chips = "".join(
    f'<span style="display:inline-block; background:#FFFFFF; border:1px solid #E2E1DB; '
    f'border-radius:20px; padding:6px 16px; margin:0 8px 8px 0; font-size:12.5px; '
    f'font-weight:600; color:#22303F;">{d}</span>'
    for d in domains
)
st.markdown(f'<div style="margin-bottom:24px;">{chips}</div>', unsafe_allow_html=True)

st.divider()

section_title("How It Works", "One continuous journey — no manual handoff between tools")

steps = [
    ("1. Onboard", "Upload files or connect a source"),
    ("2. AI Analysis", "20-step pipeline: relationships, facts, dimensions, quality, security"),
    ("3. Semantic Model", "A governed, reviewable model — facts, dimensions, metrics, glossary"),
    ("4. Analytics", "Dashboards, KPIs, and Ask AI — generated from metadata, not code"),
]
cols = st.columns(4)
for col, (title, desc) in zip(cols, steps):
    with col:
        with st.container(border=True):
            st.markdown(f"**{title}**")
            st.caption(desc)

st.divider()

with st.container(border=True):
    col_a, col_b = st.columns([3, 1])
    with col_a:
        section_title("Platform Status")
        if security.is_configured():
            st.markdown('<span class="platform-tag ok">● Connected to Databricks</span>', unsafe_allow_html=True)
            st.caption(f"Catalog: `{st.secrets.get('DATABRICKS_CATALOG', 'not set')}`")
        else:
            st.markdown('<span class="platform-tag pii">● Not configured</span>', unsafe_allow_html=True)
            st.caption("Databricks secrets are not configured for this deployment. See README.md.")
    with col_b:
        if st.button("Security Center →"):
            navigate_to("Security Center")

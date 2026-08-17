from pathlib import Path
import runpy
import streamlit as st
from theme import inject_base_css, render_sidebar_brand, render_sidebar_navigation, render_user_identity
from auth import auth_enabled, require_login, can_access, current_user

st.set_page_config(page_title='C INVENT — Enterprise Semantic Analytics',page_icon='C',layout='wide',initial_sidebar_state='expanded')
inject_base_css()

# C INVENT authentication gate.
# This MUST execute before any navigation/router/page dispatch.
if auth_enabled():
    if not require_login():
        st.stop()

# F5/browser refresh must return to Home, while normal button reruns retain the page.
try:
    from streamlit_js_eval import streamlit_js_eval
    nav_type=streamlit_js_eval(js_expressions="performance.getEntriesByType('navigation')[0]?.type || 'navigate'",key='invent_navigation_type')
    if nav_type=='reload' and not st.session_state.get('_reload_home_handled'):
        st.session_state['_invent_current_page']='Home'
        st.session_state['_reload_home_handled']=True
except Exception:
    pass

if '_invent_current_page' not in st.session_state:
    st.session_state['_invent_current_page']='Home'
render_sidebar_brand(); render_sidebar_navigation(); render_user_identity()
VIEWS={
'Home':'0_Home.py','Data Onboarding':'1_Data_Onboarding.py','AI Analysis':'2_AI_Analysis.py','Semantic Intelligence':'3_Semantic_Intelligence.py','Business Model':'4_Business_Model.py','QA Validation':'9_QA_Validation.py','Analytics':'5_Analytics.py','Ask AI':'6_Ask_AI.py','Genie Agent':'8_Genie.py','Security Center':'7_Security_Center.py','Databricks Discovery':'10_Databricks_Discovery.py','Connectors':'11_Connectors.py','Audit & Policies':'12_Audit.py'}
current=st.session_state.get('_invent_current_page','Home')
if not can_access(current):
    st.session_state['_invent_current_page']='Home'
    current='Home'
path=Path(__file__).parent/'views'/VIEWS.get(current,VIEWS['Home'])
if not path.exists(): st.error(f'Missing C INVENT view: {path.name}'); st.stop()
runpy.run_path(str(path),run_name='__invent_view__')

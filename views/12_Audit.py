import streamlit as st
from theme import page_header, section_title
page_header('Audit & Policies','Publication and governance events visible in the current C INVENT session.')
logs=st.session_state.get('invent_audit',[])
if not logs: st.info('No C INVENT publish events in this session yet.')
for item in reversed(logs):
    with st.container(border=True): st.markdown(f"**{item.get('event','Publish')}** · `{item.get('domain','')}`"); st.caption(item.get('detail',''))
section_title('Policy Guarantees')
st.markdown('- One domain → one canonical Metric View: `mv_domain`\n- All detected facts → real Delta tables\n- Legacy per-fact `mv_*` views are removed during republish\n- Genie registration is domain-scoped and idempotent\n- Ask AI is restricted to governed Metric View metadata')

import streamlit as st
from theme import page_header, section_title
import security_fabric as security
import discovery_engine as discovery

page_header('Databricks Discovery','Live Unity Catalog discovery — catalogs, schemas, tables, columns, relationships and Metric Views.')
if not security.is_configured():
    st.markdown('<div class="platform-banner warn">Databricks is not configured. Add DATABRICKS_HOST, DATABRICKS_TOKEN, DATABRICKS_WAREHOUSE_ID and DATABRICKS_CATALOG to Streamlit Secrets.</div>', unsafe_allow_html=True)
    st.stop()

try:
    catalogs = discovery.list_catalogs()
except Exception as e:
    st.error(f'Unity Catalog discovery failed: {e}')
    st.caption('C INVENT uses Databricks SQL INFORMATION_SCHEMA for discovery so it works across Databricks Free Edition/workspace API variations.')
    st.stop()

preferred = st.secrets.get('DATABRICKS_CATALOG','')
idx = catalogs.index(preferred) if preferred in catalogs else 0
catalog = st.selectbox('Catalog', catalogs, index=idx if catalogs else 0)

c_refresh, c_status = st.columns([1, 3])
with c_refresh:
    if st.button('↻ Refresh Discovery', type='primary', use_container_width=True):
        st.cache_data.clear()
        st.rerun()
with c_status:
    st.caption(f'Connected to Unity Catalog through the configured SQL warehouse · `{catalog}`')

if not catalog:
    st.stop()

try:
    result = discovery.discover_catalog(catalog)
    schemas = result['schemas']; tables = result['tables']; mvs = result['metric_views']
    columns = result['columns']; relationships = result['relationships']

    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric('Schemas', len(schemas))
    c2.metric('Relations', len(tables))
    c3.metric('Metric Views', len(mvs))
    c4.metric('Columns', len(columns))
    c5.metric('Declared FKs', len(relationships))

    st.divider()
    section_title('Metric Views','Authoritative Metric View metadata is read from Databricks DESCRIBE TABLE ... AS JSON.')
    if mvs.empty:
        st.info('No Metric Views are visible to the configured identity in this catalog. If you have a published mv_domain, verify SELECT/USE SCHEMA privileges and refresh discovery.')
    else:
        for _, row in mvs.iterrows():
            with st.container(border=True):
                left, right = st.columns([5,1])
                with left:
                    st.markdown(f"**{row['full_name']}**")
                    st.caption(f"Type: `{row['table_type']}` · Schema: `{row['schema_name']}`")
                with right:
                    if st.button('Inspect', key='inspect_'+str(row['full_name'])):
                        st.session_state['discovery_selected_mv'] = row['full_name']
                        st.rerun()

    selected = st.session_state.get('discovery_selected_mv')
    if selected:
        detail = discovery.metric_view_details(selected)
        st.divider()
        section_title('Metric View Metadata', selected)
        a,b,c = st.columns(3)
        a.write('**Type:** ' + str(detail.get('table_type')))
        b.write('**Owner:** ' + str(detail.get('owner')))
        c.write('**Language:** ' + str(detail.get('language') or '—'))
        if detail['columns'].empty:
            st.info('No columns returned.')
        else:
            st.dataframe(detail['columns'], use_container_width=True, hide_index=True)
        if detail.get('view_definition'):
            with st.expander('Metric View definition / YAML', expanded=False):
                st.code(detail['view_definition'], language='yaml')

    st.divider()
    section_title('Unity Catalog Relations','Real tables and views visible to the configured identity.')
    if not tables.empty:
        st.dataframe(tables[['full_name','table_type','owner','comment']], use_container_width=True, hide_index=True)
    else:
        st.info('No relations are visible to this identity.')

    st.divider()
    section_title('Columns','Live column metadata from Unity Catalog INFORMATION_SCHEMA.COLUMNS.')
    st.dataframe(columns, use_container_width=True, hide_index=True)

    st.divider()
    section_title('Relationships','Declared Unity Catalog foreign-key relationships. These are not guessed from column names.')
    if relationships.empty:
        st.info('No declared foreign-key relationships are exposed for this catalog. C INVENT does not fabricate relationships in the live discovery view.')
    else:
        st.dataframe(relationships, use_container_width=True, hide_index=True)

    st.divider()
    section_title('Schemas')
    st.dataframe(schemas, use_container_width=True, hide_index=True)
except Exception as e:
    st.error(f'Discovery error: {e}')

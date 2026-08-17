import streamlit as st
from theme import page_header, section_title
page_header('Connectors','Enterprise source entry points. File formats are fully enabled; connector adapters expose configuration without pretending to be connected.')
connectors=[('Databricks / Unity Catalog','Live discovery and SQL execution','Connected' if all(k in st.secrets for k in ['DATABRICKS_HOST','DATABRICKS_TOKEN','DATABRICKS_WAREHOUSE_ID','DATABRICKS_CATALOG']) else 'Not configured'),('Snowflake','Connector boundary','Adapter ready'),('PostgreSQL','Connector boundary','Adapter ready'),('MySQL','Connector boundary','Adapter ready'),('SQL Server','Connector boundary','Adapter ready'),('Oracle','Connector boundary','Adapter ready'),('Amazon S3','Object storage','Adapter ready'),('Azure Data Lake','Object storage','Adapter ready'),('Google BigQuery','Cloud warehouse','Adapter ready'),('JDBC','Generic JDBC','Adapter ready')]
for i in range(0,len(connectors),2):
    cols=st.columns(2)
    for col,(name,desc,status) in zip(cols,connectors[i:i+2]):
        with col,st.container(border=True):
            st.markdown(f'**{name}**')
            st.caption(desc)
            st.markdown(f'<span class="platform-tag ok">● {status}</span>' if status=='Connected' else f'<span class="platform-tag ai">{status}</span>',unsafe_allow_html=True)
st.divider(); section_title('Supported Source Files')
st.markdown('**CSV · XLSX · XLS · JSON · PARQUET · XML**')
st.caption('Parquet uses pyarrow; XML uses pandas ElementTree. Both are enabled in the production requirements.')

"""Interactive screening UI. Run with: streamlit run app.py"""
import streamlit as st
from sqlalchemy import create_engine

from src.config import database_url
from src.ui.classroom import show_classroom
from src.ui.waterbody_workflow import show_st37_inventory

st.set_page_config(page_title='Alberta well screening', page_icon='🌿', layout='wide')


@st.cache_resource
def connection_pool(url):
    return create_engine(url, pool_pre_ping=True)


def main():
    st.title('Alberta well screening')
    st.caption('Educational proximity screening — not an environmental risk assessment or an operational recommendation.')
    mode = st.sidebar.selectbox('Dataset mode', ['Classroom demo', 'ST37 well inventory'],
                                key='dataset_mode', bind='query-params')
    if st.session_state.get('previous_dataset_mode') != mode:
        st.session_state.previous_dataset_mode = mode
        st.session_state.pop('classroom_scope', None)
    if mode == 'Classroom demo':
        show_classroom()
        return
    try:
        engine = connection_pool(database_url())
    except Exception:
        st.error('Configure DATABASE_URL for local PostgreSQL/PostGIS using README.md, then restart the app.')
        st.stop()
    st.session_state.setdefault('busy', False)
    st.session_state.setdefault('actions', [])
    show_st37_inventory(engine)


main()

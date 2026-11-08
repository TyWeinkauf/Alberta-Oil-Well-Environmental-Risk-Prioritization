"""Production presentation never aggregates incompatible products/activities/units."""
import json

import pandas as pd
import streamlit as st


def show_well_production(view: dict):
    st.subheader('Monthly production')
    batch=view['batch']
    if batch and batch['source_mode']=='synthetic':
        st.caption('Synthetic production demonstration — these observations are not Petrinex data.')
    if not view['verified']:
        st.info('Well-level production not available/verified. No facility volumes have been allocated to this well.')
        return
    frame=pd.DataFrame(view['verified'])
    series=sorted(frame[['product','activity','unit']].drop_duplicates().itertuples(index=False,name=None),
                  key=lambda key:(-len(frame[(frame['product']==key[0])&(frame['activity']==key[1])&(frame['unit']==key[2])]),key))
    selected=st.selectbox('Production series',series,format_func=lambda key:f'{key[0]} · {key[1]} ({key[2]})')
    shown=frame[(frame['product']==selected[0])&(frame['activity']==selected[1])&(frame['unit']==selected[2])].copy()
    chart=pd.DataFrame({'Month':pd.to_datetime(shown['period']+'-01'),'Reported volume':shown['volume'].astype(float)})
    st.caption(f'Latest reported month: {shown["period"].max()} · unit: {selected[2]} · exact, uniquely verified source identifiers')
    if shown['period'].duplicated().any():
        st.caption('Multiple records occur in a month; each observation is displayed separately without summing.')
        st.scatter_chart(chart,x='Month',y='Reported volume')
    else:st.line_chart(chart,x='Month',y='Reported volume')
    st.dataframe(shown,hide_index=True)
    st.caption('Products, activities and units are shown separately. Missing months are not filled with zeros; facility totals are never allocated to wells.')


def show_production_audit(view: dict):
    st.subheader('Production attribution audit')
    if not view['batch']:
        st.caption('No production batch has been imported for this dataset.')
        return
    batch=view['batch']
    st.caption(f'Active batch {batch["batch_id"]} · {batch["source_mode"]} · {batch["window_start"][:7]} to {batch["window_end"][:7]}')
    st.json(batch['validation'])
    st.dataframe(pd.DataFrame(view['audit']),hide_index=True)
    st.caption('Facility, unmatched, ambiguous and unknown observations remain auditable; only verified well-level links enter a well chart.')
    st.dataframe(pd.DataFrame(view['quarantine']),hide_index=True)
    st.download_button('Download production audit',json.dumps(view,indent=2).encode(),
                       'production_audit.json','application/json',on_click='ignore')

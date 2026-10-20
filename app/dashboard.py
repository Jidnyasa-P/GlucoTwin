from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from glucotwin.data import load_demo_data
from glucotwin.twin import DigitalTwin
from glucotwin.forecast import train_default_model

st.set_page_config(page_title='GlucoTwin | Research prototype',layout='wide')
st.title('GlucoTwin')
st.caption('Explainable glucose digital-twin proof of concept · SYNTHETIC DATA · NOT FOR CLINICAL USE')
st.warning('Research/education only. Not clinically validated. Do not use for diagnosis, treatment, insulin dosing, or medication decisions.')
@st.cache_resource
def get_model(): return train_default_model(seed=42)[0]
if 'twin' not in st.session_state:
    profile,obs=load_demo_data(); st.session_state.twin=DigitalTwin(profile,obs,db_path=str(ROOT/'data/glucotwin_audit.jsonl'))
twin=st.session_state.twin
profile=twin.profile; obs=twin.observations
with st.sidebar:
    st.header('Virtual patient')
    st.write('**ID:**',profile.get('patient_id'))
    st.write('**Provenance:**',profile.get('provenance','UNKNOWN'))
    st.write('**Age (synthetic):**',profile.get('age_years','Not available'))
    st.write('**History:**',profile.get('diabetes_type','Not available'))
    st.write('**HbA1c (synthetic):**',profile.get('hba1c_percent','Not available'),'%')
    st.caption('Historical fields are state context and model features; the forecast uses age, diabetes duration, HbA1c, and recent glucose lags.')
    simulate_stale=st.checkbox('Simulate stale stream (quality-gate test)',value=False)
quality=twin.quality(now=obs.timestamp.max()+pd.Timedelta(minutes=20 if simulate_stale else 1))
cols=st.columns(4)
cols[0].metric('Latest glucose',f"{twin.current_glucose:.1f} mg/dL")
cols[1].metric('Observations',len(obs))
cols[2].metric('Last update',pd.Timestamp(twin.last_timestamp).strftime('%Y-%m-%d %H:%M UTC'))
cols[3].metric('Data status',quality['status'])
for warning in quality['warnings']: st.warning(warning)

st.subheader('Observed glucose and forecast')
model=get_model()
if st.button('Generate / refresh forecast',type='primary',disabled=not quality['forecast_allowed']):
    if len(obs)>=12:
        f=model.predict(obs.glucose_mg_dl.tail(12).tolist(),obs.timestamp.max(),horizon_steps=24,profile=profile)
        twin.set_forecast(f); st.session_state.last_forecast=f
    else: st.error('At least 12 readings are required.')
f=twin.latest_forecast
fig=go.Figure()
fig.add_trace(go.Scatter(x=obs.timestamp.tail(72),y=obs.glucose_mg_dl.tail(72),name='Observed (synthetic)',mode='lines+markers',line=dict(color='#2878B5')))
if f:
    x=pd.to_datetime(f.timestamps,utc=True)
    fig.add_trace(go.Scatter(x=x,y=f.upper_mg_dl,mode='lines',line=dict(width=0),showlegend=False,hoverinfo='skip'))
    fig.add_trace(go.Scatter(x=x,y=f.lower_mg_dl,mode='lines',line=dict(width=0),fill='tonexty',fillcolor='rgba(240,160,50,0.18)',name='Illustrative uncertainty band',hoverinfo='skip'))
    fig.add_trace(go.Scatter(x=x,y=f.values_mg_dl,name='Model forecast (research)',mode='lines+markers',line=dict(color='#E08B24',dash='dash')))
fig.update_layout(xaxis_title='Timestamp (UTC)',yaxis_title='Glucose (mg/dL)',legend_orientation='h',height=430)
st.plotly_chart(fig,use_container_width=True)
if f:
    st.caption(f'Model: {f.model_version}. Forecast generated at {pd.Timestamp.now(tz="UTC").isoformat()}. Interval is a heuristic band derived from synthetic training residuals and is not clinically calibrated.')
    st.subheader('Inputs associated with forecast')
    st.dataframe(pd.DataFrame(f.explanation),use_container_width=True,hide_index=True)
    st.caption('These are descriptive input summaries, not causal attributions or SHAP values.')

st.subheader('Inject a new observation')
with st.form('new_reading'):
    new_value=st.number_input('Glucose (mg/dL)',min_value=20.0,max_value=600.0,value=float(twin.current_glucose or 120),step=1.0)
    new_time=st.text_input('Timestamp (ISO 8601; UTC recommended)',value=(pd.Timestamp(twin.last_timestamp)+pd.Timedelta(minutes=5)).isoformat())
    submitted=st.form_submit_button('Ingest reading')
if submitted:
    result=twin.ingest(new_time,new_value)
    if result['accepted']:
        st.success('Observation accepted. State updated; previous forecast cleared so a fresh forecast is required.')
        st.rerun()
    else: st.error(f"Observation rejected: {result['reason']}")

st.subheader('What-if scenario lab')
st.caption('Hypothetical model perturbation only. This is not a treatment simulator and does not estimate intervention effects.')
perturb=st.slider('Hypothetical offset to recent glucose inputs (mg/dL)',-30,30,0,5)
if st.button('Compare hypothetical scenario'):
    if len(obs)>=12:
        baseline=model.predict(obs.glucose_mg_dl.tail(12).tolist(),obs.timestamp.max(),horizon_steps=12,profile=profile)
        scenario=model.predict((obs.glucose_mg_dl.tail(12)+perturb).tolist(),obs.timestamp.max(),horizon_steps=12,profile=profile)
        st.write({'scenario':'SYNTHETIC WHAT-IF — NOT CAUSAL','input_offset_mg_dl':perturb,'baseline_30_min':baseline.values_mg_dl[5],'scenario_30_min':scenario.values_mg_dl[5],'difference_mg_dl':round(scenario.values_mg_dl[5]-baseline.values_mg_dl[5],2)})

with st.expander('Data quality and audit history'):
    st.json(twin.state_summary())
    st.dataframe(pd.DataFrame(twin.audit),use_container_width=True,hide_index=True)
    st.write('Forecast history in this session:',len(twin.forecast_history))
    st.write('Observation source labels:',sorted(set(obs.provenance.astype(str))))
st.subheader('Evaluation')
report_path=ROOT/'experiments/benchmark_report.md'
if report_path.exists(): st.markdown(report_path.read_text())
else: st.info('Run `python scripts/evaluate.py` to generate the benchmark report.')

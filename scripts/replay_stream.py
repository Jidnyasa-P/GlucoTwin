from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from glucotwin.data import load_demo_data
from glucotwin.twin import DigitalTwin
profile,obs=load_demo_data(); twin=DigitalTwin(profile,obs,db_path='data/replay_audit.jsonl')
print('Initial:',twin.state_summary())
ts=twin.last_timestamp+__import__('pandas').Timedelta(minutes=5)
print('Ingest:',twin.ingest(ts,float(twin.current_glucose+4)))
print('Updated:',twin.state_summary())

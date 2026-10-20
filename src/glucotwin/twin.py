from __future__ import annotations
import json
from pathlib import Path
import pandas as pd
from .quality import validate_observation, quality_status
from .features import make_feature_row

class DigitalTwin:
    def __init__(self, profile: dict, observations: pd.DataFrame, db_path="data/glucotwin_audit.jsonl"):
        self.profile=dict(profile); self.observations=observations.copy().sort_values("timestamp").reset_index(drop=True)
        self.db_path=Path(db_path); self.audit=[]; self.forecast_history=[]; self.latest_forecast=None
        self._audit("initialized", {"patient_id":self.profile.get("patient_id"),"observation_count":len(self.observations)})
    def _audit(self,event,details):
        record={"event":event,"at":pd.Timestamp.now(tz="UTC").isoformat(),"details":details}
        self.audit.append(record)
        try:
            self.db_path.parent.mkdir(parents=True,exist_ok=True)
            with self.db_path.open("a",encoding="utf-8") as f: f.write(json.dumps(record,default=str)+"\n")
        except OSError: pass
    @property
    def current_glucose(self): return float(self.observations.iloc[-1].glucose_mg_dl) if not self.observations.empty else None
    @property
    def last_timestamp(self): return self.observations.iloc[-1].timestamp if not self.observations.empty else None
    def quality(self, now=None): return quality_status(self.observations,now=now)
    def ingest(self,timestamp,glucose_mg_dl,provenance="USER-ENTERED DEMO OBSERVATION"):
        ok,ts,reason=validate_observation(timestamp,glucose_mg_dl,self.observations)
        if not ok:
            self._audit("observation_rejected",{"reason":reason,"timestamp":str(timestamp)})
            return {"accepted":False,"reason":reason}
        row={"patient_id":self.profile.get("patient_id","UNKNOWN"),"timestamp":ts,"glucose_mg_dl":float(glucose_mg_dl),"provenance":provenance}
        self.observations=pd.concat([self.observations,pd.DataFrame([row])],ignore_index=True).sort_values("timestamp").reset_index(drop=True)
        self.latest_forecast=None
        self._audit("observation_accepted",{"timestamp":ts.isoformat(),"glucose_mg_dl":float(glucose_mg_dl),"provenance":provenance})
        return {"accepted":True,"reason":"accepted","quality":self.quality(now=ts+pd.Timedelta(minutes=1))}
    def set_forecast(self,forecast):
        self.latest_forecast=forecast; self.forecast_history.append(forecast)
        self._audit("forecast_generated",{"model_version":forecast.model_version,"points":len(forecast.values_mg_dl)})
    def state_summary(self):
        return {"patient_id":self.profile.get("patient_id"),"profile_provenance":self.profile.get("provenance","UNKNOWN"),"current_glucose_mg_dl":self.current_glucose,"last_timestamp":str(self.last_timestamp),"observation_count":len(self.observations),"quality":self.quality(),"forecast_count":len(self.forecast_history)}

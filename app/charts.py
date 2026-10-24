"""Plotly figure builders. Observed = solid blue with markers; forecast = dashed red with shaded interval."""
from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd
import plotly.graph_objects as go

from glucotwin.config import HORIZONS_MIN, LOCAL_TZ, UNIT

OBS, FC, SC, TRUTH = "#1f77b4", "#d62728", "#7b3fb0", "#7f7f7f"


def _loc(ts):
    return pd.DatetimeIndex(pd.to_datetime(ts, utc=True)).tz_convert(LOCAL_TZ)


def forecast_figure(state: Dict, truth: Optional[pd.Series] = None, hours_back: float = 6, fc: Optional[Dict] = None,
                    title: str = "Observed glucose and model forecast") -> go.Figure:
    fig = go.Figure()
    rec = state["recent"]
    obs = pd.Series([v for _, v in rec], index=_loc([t for t, _ in rec]))
    if len(obs):
        obs = obs[obs.index >= obs.index.max() - pd.Timedelta(hours=hours_back)]
        fig.add_trace(go.Scatter(x=obs.index, y=obs.values, mode="lines+markers", name="Observed (CGM)",
                                 line=dict(color=OBS, width=2), marker=dict(size=5),
                                 hovertemplate=f"%{{x|%d %b %H:%M}} IST<br>%{{y:.0f}} {UNIT} (observed)<extra></extra>"))
    fc = fc or state.get("latest_forecast")
    if fc:
        t0 = pd.Timestamp(fc["as_of_ts"])
        xs = _loc([t0] + [t0 + pd.Timedelta(minutes=h) for h in fc["horizons_min"]])
        last_obs = fc["inputs"]["window_mg_dl"][-1] if fc.get("inputs") else fc["values"][0]
        ys = [last_obs] + fc["values"]
        if fc.get("lower"):
            lo, hi = [last_obs] + fc["lower"], [last_obs] + fc["upper"]
            fig.add_trace(go.Scatter(x=list(xs) + list(xs[::-1]), y=hi + lo[::-1], fill="toself", fillcolor="rgba(214,39,40,0.15)",
                                     line=dict(width=0), name=f"{int(round(fc['interval_nominal'] * 100))}% prediction interval",
                                     hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines+markers", name="Forecast (model, NOT observed)",
                                 line=dict(color=FC, width=2, dash="dash"), marker=dict(size=6, symbol="diamond"),
                                 hovertemplate=f"%{{x|%d %b %H:%M}} IST<br>%{{y:.0f}} {UNIT} (forecast)<extra></extra>"))
        fig.add_vline(x=xs[0], line=dict(color="#555", dash="dot"), annotation_text="forecast origin", annotation_position="top left")
    if truth is not None and len(truth):
        fig.add_trace(go.Scatter(x=_loc(truth.index), y=truth.values, mode="lines+markers", name="Recorded later values (replay only; never a model input)",
                                 line=dict(color=TRUTH, width=1.5, dash="dot"), marker=dict(size=4)))
    for y, lab in ((70, "70"), (180, "180")):
        fig.add_hline(y=y, line=dict(color="#aaa", width=1, dash="dot"), annotation_text=f"{lab} {UNIT} reference", annotation_position="bottom right")
    fig.update_layout(title=title, xaxis_title=f"Time ({LOCAL_TZ}, IST)", yaxis_title=f"Glucose ({UNIT})", height=440,
                      legend=dict(orientation="h", y=-0.25), margin=dict(l=10, r=10, t=50, b=10), hovermode="x unified")
    return fig


def contribution_figure(expl: Dict, horizon: int, top: int = 10) -> go.Figure:
    h = expl["horizons"][str(horizon)]
    items = h["contributions"][:top][::-1]
    fig = go.Figure(go.Bar(x=[i["contribution"] for i in items], y=[f"{i['label']} = {i['value']:.1f}" for i in items], orientation="h",
                           marker_color=["#d62728" if i["contribution"] > 0 else "#1f77b4" for i in items],
                           hovertemplate="%{y}<br>%{x:+.2f} mg/dL<extra></extra>"))
    fig.update_layout(title=f"Contributions to the predicted change at +{horizon} min (base {h['base_value']:+.1f}, total {h['predicted_change']:+.1f} mg/dL)",
                      xaxis_title="mg/dL added to / subtracted from the forecast change vs latest reading", height=420,
                      margin=dict(l=10, r=10, t=60, b=10))
    return fig


def scenario_figure(sc: Dict, state: Dict) -> go.Figure:
    t0 = pd.Timestamp(sc["as_of"])
    xs = _loc([t0 + pd.Timedelta(minutes=h) for h in sc["horizons_min"]])
    fig = go.Figure()
    for key, name, col, dash in (("base", "Original forecast", FC, "dash"), ("scenario", "HYPOTHETICAL scenario forecast", SC, "dash")):
        d = sc[key]
        fig.add_trace(go.Scatter(x=list(xs) + list(xs[::-1]), y=d["upper"] + d["lower"][::-1], fill="toself", line=dict(width=0),
                                 fillcolor="rgba(214,39,40,0.10)" if key == "base" else "rgba(123,63,176,0.12)", hoverinfo="skip", showlegend=False))
        fig.add_trace(go.Scatter(x=xs, y=d["values"], mode="lines+markers", name=name, line=dict(color=col, dash=dash, width=2)))
    rec = state["recent"][-8:]
    fig.add_trace(go.Scatter(x=_loc([t for t, _ in rec]), y=[v for _, v in rec], mode="lines+markers", name="Observed (CGM)", line=dict(color=OBS)))
    fig.update_layout(title="Model-based hypothetical comparison (not a treatment effect)", yaxis_title=f"Glucose ({UNIT})",
                      xaxis_title=f"Time ({LOCAL_TZ}, IST)", height=420, legend=dict(orientation="h", y=-0.25), margin=dict(l=10, r=10, t=50, b=10))
    return fig


def context_figure(ctx: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Bar(x=_loc(ctx["timestamp"]), y=ctx["steps"], name="steps / 15 min", marker_color="#8fbf8f"))
    fig.add_trace(go.Scatter(x=_loc(ctx["timestamp"]), y=ctx["heart_rate_bpm"], name="heart rate (bpm)", yaxis="y2", line=dict(color="#e08a3c")))
    fig.update_layout(title="SYNTHETIC wearable context stream (UI demonstration only; NOT used by the model)", height=260,
                      yaxis=dict(title="steps"), yaxis2=dict(title="bpm", overlaying="y", side="right"),
                      legend=dict(orientation="h", y=-0.3), margin=dict(l=10, r=10, t=50, b=10))
    return fig

"""AI demand forecasting (F11).

Gradient-boosted trees (Poisson loss) predict bookings per zone × service × time block
for the next 7 days. Features are calendar signals (weekday, month, monsoon,
festival window, trend) plus lagged demand (1–4 weeks back), so every prediction
is explainable. Trained on synthetic history — the pipeline is real, the data is not.
"""
from datetime import timedelta

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance

from core import db
from core.config import FESTIVAL_WINDOW_DAYS, FESTIVALS, MONSOON, SERVICES, TIME_BLOCKS, ZONES, today

FEATURES = ["zone_i", "service_i", "block_i", "dow", "month", "weekend", "monsoon", "festival",
            "lag7", "lag14", "lag_mean4"]
FEATURE_LABELS = {
    "zone_i": "Zone", "service_i": "Service type", "block_i": "Time of day", "dow": "Day of week",
    "month": "Month (season)", "weekend": "Weekend", "monsoon": "Monsoon", "festival": "Festival window",
    "t": "Growth trend", "lag7": "Demand 1 week ago", "lag14": "Demand 2 weeks ago",
    "lag_mean4": "Avg demand, last 4 weeks",
}
Z_IDX = {z["zone_id"]: i for i, z in enumerate(ZONES)}
S_IDX = {s["service_id"]: i for i, s in enumerate(SERVICES)}
B_IDX = {b["id"]: i for i, b in enumerate(TIME_BLOCKS)}


def _is_monsoon(d):
    ms, md, me, mde = MONSOON
    return int((d.month, d.day) >= (ms, md) and (d.month, d.day) <= (me, mde))


def _is_festival(d):
    return int(any(0 <= (f - d).days <= FESTIVAL_WINDOW_DAYS for _, f in FESTIVALS))


def _calendar(df, t0):
    d = pd.to_datetime(df.date)
    df["dow"] = d.dt.dayofweek
    df["month"] = d.dt.month
    df["weekend"] = (df.dow >= 5).astype(int)
    dd = d.dt.date
    df["monsoon"] = dd.map(_is_monsoon)
    df["festival"] = dd.map(_is_festival)
    df["t"] = (d - t0).dt.days
    df["zone_i"] = df.zone_id.map(Z_IDX)
    df["service_i"] = df.service_id.map(S_IDX)
    df["block_i"] = df.block.map(B_IDX)
    return df


def _add_lags(full):
    full = full.sort_values(["zone_id", "service_id", "block", "date"])
    g = full.groupby(["zone_id", "service_id", "block"]).bookings
    full["lag7"] = g.shift(7)
    full["lag14"] = g.shift(14)
    full["lag21"] = g.shift(21)
    full["lag28"] = g.shift(28)
    full["lag_mean4"] = full[["lag7", "lag14", "lag21", "lag28"]].mean(axis=1)
    return full


def _model():
    return HistGradientBoostingRegressor(loss="poisson", max_iter=250, learning_rate=0.08,
                                         max_leaf_nodes=31, categorical_features=[0, 1, 2], random_state=7)


def train():
    """Returns dict(model, metrics, holdout, importance, t0, history)."""
    hist = db.q("select * from demand_history")
    t0 = pd.Timestamp(hist.date.min())
    full = _add_lags(_calendar(hist.copy(), t0)).dropna(subset=["lag28"])
    cutoff = (pd.Timestamp(hist.date.max()) - pd.Timedelta(days=27)).strftime("%Y-%m-%d")
    tr, te = full[full.date < cutoff], full[full.date >= cutoff]
    m = _model().fit(tr[FEATURES], tr.bookings)
    te = te.copy()
    te["pred"] = m.predict(te[FEATURES])

    def wape(a, p):
        return float(np.abs(a - p).sum() / max(a.sum(), 1))

    daily_zs = te.groupby(["date", "zone_id", "service_id"])[["bookings", "pred"]].sum()
    daily_s = te.groupby(["date", "service_id"])[["bookings", "pred"]].sum()
    metrics = {
        "wape_zone_service_day": wape(daily_zs.bookings, daily_zs.pred),
        "wape_service_day": wape(daily_s.bookings, daily_s.pred),
        "mape_service_day": float((np.abs(daily_s.bookings - daily_s.pred) / daily_s.bookings.clip(lower=1)).mean()),
        "per_service": {s: wape(g.bookings, g.pred) for s, g in daily_s.groupby(level="service_id")},
        "train_rows": len(tr), "test_rows": len(te), "cutoff": cutoff,
    }
    sample = te.sample(min(6000, len(te)), random_state=1)
    pi = permutation_importance(m, sample[FEATURES], sample.bookings, n_repeats=3, random_state=1,
                                scoring="neg_mean_absolute_error")
    importance = (pd.DataFrame({"feature": FEATURES, "importance": pi.importances_mean})
                  .assign(label=lambda d: d.feature.map(FEATURE_LABELS))
                  .sort_values("importance", ascending=False))
    final = _model().fit(full[FEATURES], full.bookings)
    return {"model": final, "metrics": metrics, "holdout": daily_s.reset_index(), "importance": importance,
            "t0": t0, "history": hist}


def predict_next(bundle, days: int = 7, spike: bool = False) -> pd.DataFrame:
    hist = bundle["history"]
    start = today()
    future = []
    for k in range(days):
        d = (start + timedelta(days=k)).isoformat()
        for z in ZONES:
            for s in SERVICES:
                for b in TIME_BLOCKS:
                    future.append((d, b["id"], z["zone_id"], s["service_id"], np.nan))
    fut = pd.DataFrame(future, columns=hist.columns)
    full = pd.concat([hist, fut], ignore_index=True)
    full = _add_lags(_calendar(full, bundle["t0"]))
    fut = full[full.bookings.isna()].copy()
    # lag7 for the first forecast days comes from history; fill any gap with the 4-week mean
    fut["lag7"] = fut.lag7.fillna(fut.lag_mean4)
    fut["pred"] = bundle["model"].predict(fut[FEATURES])
    if spike:
        # Heavy-rain alert scenario: plumbing & electrical surge in Mira–Bhayandar and Thane for 3 days
        mask = (fut.service_id.isin(["S1", "S2"]) & fut.zone_id.isin(["Z01", "Z02", "Z07", "Z08"])
                & (pd.to_datetime(fut.date) < pd.Timestamp(start + timedelta(days=3))))
        fut.loc[mask, "pred"] *= 1.8
    return fut[["date", "block", "zone_id", "service_id", "pred"]].reset_index(drop=True)

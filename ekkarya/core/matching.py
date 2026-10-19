"""Deterministic, explainable worker matching (PRD 10.5 / F17).

score = 0.40 × proximity + 0.25 × rating + 0.15 × certification + 0.20 × fairness

The fairness term rotates work across cooperative members — this is where the
cooperative principle shows up in the algorithm.
"""
import numpy as np
import pandas as pd

from core import db
from core.config import (MIN_SEARCH_KM, SHIFT_BLOCKS, W_CERT, W_FAIR, W_PROXIMITY, W_RATING,
                         current_block, now)


def haversine(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp, dl = p2 - p1, np.radians(np.asarray(lon2) - lon1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def busy_workers() -> set:
    df = db.q("select distinct worker_id from bookings where status in ('en_route','in_progress') "
              "and worker_id is not null")
    return set(df.worker_id)


def candidates(booking: dict, emergency: bool = False, max_km: float | None = None) -> pd.DataFrame:
    """Return eligible workers for a booking with score components, best first."""
    w = db.q("""select w.*, s.certified as skill_cert, s.years_exp as skill_years
                from workers w join worker_skills s
                  on s.worker_id = w.worker_id and s.service_id = ?
                where w.kyc_status = 'verified' and w.is_online = 1""", (booking["service_id"],))
    if w.empty:
        return w
    w = w[~w.worker_id.isin(busy_workers())].copy()
    if w.empty:
        return w
    w["distance_km"] = haversine(booking["lat"], booking["lon"], w.lat.values, w.lon.values)
    if emergency:
        limit = float(max_km)
        w = w[w.distance_km <= limit]
    else:
        block = booking["block"] if booking["btype"] == "scheduled" else current_block()
        w = w[w["shift"].map(lambda s: block in SHIFT_BLOCKS.get(s, []))]
        w["limit"] = w.radius_km.clip(lower=MIN_SEARCH_KM)
        w = w[w.distance_km <= w["limit"]]
        limit = None
    if w.empty:
        return w
    lim = limit if limit else w["limit"]
    w["c_proximity"] = (1 - w.distance_km / lim).clip(0, 1)
    w["c_rating"] = np.where(w.jobs_done < 5, 0.7, ((w.rating_avg - 1) / 4).clip(0, 1))
    w["c_cert"] = w.skill_cert.astype(float)
    t = now()
    hours = w.last_assigned_at.fillna("").map(
        lambda s: (t - pd.Timestamp(s).to_pydatetime()).total_seconds() / 3600 if s else 24)
    w["hours_since_job"] = hours
    w["c_fair"] = hours.clip(0, 24) / 24
    w["score"] = (W_PROXIMITY * w.c_proximity + W_RATING * w.c_rating
                  + W_CERT * w.c_cert + W_FAIR * w.c_fair)
    return w.sort_values("score", ascending=False)


def components_json(row) -> dict:
    return {
        "proximity": round(float(row["c_proximity"]), 3),
        "rating": round(float(row["c_rating"]), 3),
        "certification": round(float(row["c_cert"]), 3),
        "fairness": round(float(row["c_fair"]), 3),
        "distance_km": round(float(row["distance_km"]), 2),
        "rating_avg": round(float(row["rating_avg"]), 2),
        "hours_since_job": round(float(row["hours_since_job"]), 1),
        "score": round(float(row["score"]), 3),
    }


WEIGHTS = {"proximity": W_PROXIMITY, "rating": W_RATING, "certification": W_CERT, "fairness": W_FAIR}

"""AI workforce allocation: forecast demand vs. available supply (F11).

supply(zone, service, block) = verified workers with that skill whose shift covers the block
capacity = supply × JOBS_PER_BLOCK
gap = capacity − forecast demand   (negative = shortage)
"""
import math

import numpy as np
import pandas as pd

from core import db
from core.config import JOBS_PER_BLOCK, SHIFT_BLOCKS, ZONE_BY_ID
from core.matching import haversine


def supply() -> pd.DataFrame:
    w = db.q("""select w.worker_id, w.zone_id, w.shift, s.service_id from workers w
                join worker_skills s on s.worker_id=w.worker_id where w.kyc_status='verified'""")
    w["block"] = w["shift"].map(SHIFT_BLOCKS)
    w = w.explode("block")
    return (w.groupby(["zone_id", "service_id", "block"]).worker_id.nunique()
            .rename("workers").reset_index())


def gaps(forecast: pd.DataFrame) -> pd.DataFrame:
    g = forecast.merge(supply(), on=["zone_id", "service_id", "block"], how="left").fillna({"workers": 0})
    g["capacity"] = g.workers * JOBS_PER_BLOCK
    g["demand"] = g.pred.round(1)
    g["gap"] = (g.capacity - g.pred).round(1)
    g["workers_needed"] = np.where(g.gap < 0, np.ceil(-g.gap / JOBS_PER_BLOCK), 0).astype(int)
    g["status"] = np.select([g.gap < -1, g.gap > JOBS_PER_BLOCK * 2], ["Shortage", "Idle capacity"], "Balanced")
    g["zone"] = g.zone_id.map(lambda z: ZONE_BY_ID[z]["name"])
    return g


def recommendations(g: pd.DataFrame, limit: int = 12) -> pd.DataFrame:
    """Move spare workers from the nearest surplus zone (same service & block) to shortage zones."""
    recs = []
    spare = {(r.date, r.block, r.service_id, r.zone_id): int(max(r.gap, 0) // JOBS_PER_BLOCK)
             for r in g.itertuples()}
    for r in g[g.workers_needed > 0].sort_values("gap").itertuples():
        need = r.workers_needed
        z = ZONE_BY_ID[r.zone_id]
        donors = g[(g.date == r.date) & (g.block == r.block) & (g.service_id == r.service_id)
                   & (g.zone_id != r.zone_id)].copy()
        donors["km"] = haversine(z["lat"], z["lon"], donors.zone_id.map(lambda x: ZONE_BY_ID[x]["lat"]).values,
                                 donors.zone_id.map(lambda x: ZONE_BY_ID[x]["lon"]).values)
        moved = []
        for d in donors.sort_values("km").itertuples():
            key = (d.date, d.block, d.service_id, d.zone_id)
            if need <= 0 or d.km > 12:
                break
            n = min(spare.get(key, 0), need)
            if n > 0:
                spare[key] -= n
                need -= n
                moved.append((d.zone_id, n, round(d.km, 1)))
        recs.append({"date": r.date, "block": r.block, "service_id": r.service_id, "zone_id": r.zone_id,
                     "demand": round(r.pred, 1), "capacity": r.capacity, "gap": r.gap,
                     "workers_needed": r.workers_needed, "moves": moved, "uncovered": need})
        if len(recs) >= limit:
            break
    return pd.DataFrame(recs)


def notify_workers(from_zone, service_id, n, message) -> int:
    """Send a notification to up to n verified workers with the skill in the donor zone."""
    from core.engine import ts
    w = db.q("""select w.worker_id from workers w join worker_skills s on s.worker_id=w.worker_id
                where w.zone_id=? and s.service_id=? and w.kyc_status='verified'
                order by w.is_demo desc, w.rating_avg desc limit ?""", (from_zone, service_id, max(int(n), 1)))
    db.executemany("insert into notifications(worker_id,message,created_at) values(?,?,?)",
                   [(wid, message, ts()) for wid in w.worker_id])
    return len(w)


def ceil_div(a, b):
    return int(math.ceil(a / b))

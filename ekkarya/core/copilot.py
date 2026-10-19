"""AI operations copilot (F16) — bounded to predefined questions.

Each question maps to a fixed pandas/SQL computation; the answer text is generated
from the computed numbers, and the evidence table is always shown beside it.
"""
from datetime import timedelta

import pandas as pd

from core import allocation, db
from core.config import COOP_BY_ID, SERVICE_NAMES_EN, ZONE_BY_ID, today

QUESTIONS = {
    "plumbers_tomorrow": "Where do we need more plumbers tomorrow?",
    "biggest_shortage": "Which zone has the biggest shortage this week?",
    "welfare_gap": "Which cooperative has the lowest welfare coverage?",
    "growth": "Which service is growing fastest?",
    "eshram": "How many workers are not yet linked to e-Shram?",
    "top_workers": "Who are the top-rated active workers?",
}


def answer(key: str, forecast_df: pd.DataFrame) -> tuple[str, pd.DataFrame]:
    if key == "plumbers_tomorrow":
        tm = (today() + timedelta(days=1)).isoformat()
        g = allocation.gaps(forecast_df[(forecast_df.date == tm) & (forecast_df.service_id == "S1")])
        s = g[g.workers_needed > 0].sort_values("gap")[["zone", "block", "demand", "capacity", "workers_needed"]]
        if s.empty:
            return "Plumbing capacity covers forecast demand in every zone tomorrow.", s
        top = s.iloc[0]
        return (f"Tomorrow, **{len(s)} zone-time slots** are short of plumbers — **{int(s.workers_needed.sum())} "
                f"more plumber-shifts** in total. The biggest gap is **{top.zone} ({top.block})**: forecast "
                f"{top.demand:.0f} jobs vs capacity {top.capacity:.0f}."), s.head(10)
    if key == "biggest_shortage":
        g = allocation.gaps(forecast_df)
        z = (g[g.gap < 0].groupby("zone").gap.sum().sort_values().rename("shortfall_jobs").round(0)
             .reset_index())
        if z.empty:
            return "No zone is short this week.", z
        return (f"**{z.iloc[0].zone}** has the largest shortfall over the next 7 days: about "
                f"**{-z.iloc[0].shortfall_jobs:.0f} jobs** beyond current capacity."), z.head(8)
    if key == "welfare_gap":
        w = db.q("""select coop_id, count(*) members, sum(insured) insured, sum(eshram_linked) eshram
                    from workers where kyc_status='verified' group by coop_id""")
        w["coverage_%"] = (w.insured / w.members * 100).round(1)
        w["cooperative"] = w.coop_id.map(lambda c: COOP_BY_ID[c]["name"])
        w = w.sort_values("coverage_%")[["cooperative", "members", "insured", "coverage_%"]]
        r = w.iloc[0]
        return (f"**{r.cooperative}** has the lowest insurance coverage at **{r['coverage_%']}%** "
                f"({int(r.members - r.insured)} verified members uninsured)."), w
    if key == "growth":
        h = db.q("select date, service_id, sum(bookings) b from demand_history group by date, service_id")
        h["date"] = pd.to_datetime(h.date)
        end = h.date.max()
        last = h[h.date > end - pd.Timedelta(days=28)].groupby("service_id").b.sum()
        prev = h[(h.date <= end - pd.Timedelta(days=28)) & (h.date > end - pd.Timedelta(days=56))].groupby("service_id").b.sum()
        g = ((last / prev - 1) * 100).round(1).rename("growth_%").reset_index()
        g["service"] = g.service_id.map(SERVICE_NAMES_EN)
        g = g.sort_values("growth_%", ascending=False)[["service", "growth_%"]]
        r = g.iloc[0]
        return (f"**{r.service}** grew fastest: **{r['growth_%']:+.1f}%** in the last 4 weeks vs the 4 weeks before."), g
    if key == "eshram":
        w = db.q("""select coop_id, count(*) members, sum(case when eshram_linked=1 then 0 else 1 end) not_linked
                    from workers where kyc_status='verified' group by coop_id""")
        w["cooperative"] = w.coop_id.map(lambda c: COOP_BY_ID[c]["name"])
        n = int(w.not_linked.sum())
        return (f"**{n} verified workers** are not yet linked to e-Shram. Help them register at a CSC or through "
                "the e-Shram portal so their welfare benefits follow them."), w[["cooperative", "members", "not_linked"]]
    if key == "top_workers":
        w = db.q("""select name, coop_id, rating_avg, jobs_done, zone_id from workers
                    where kyc_status='verified' and jobs_done>=50 order by rating_avg desc limit 10""")
        w["zone"] = w.zone_id.map(lambda z: ZONE_BY_ID[z]["name"])
        w["cooperative"] = w.coop_id.map(lambda c: COOP_BY_ID[c]["code"])
        r = w.iloc[0]
        return (f"**{r['name']}** ({r.zone}) leads with ★ {r.rating_avg:.2f} over {r.jobs_done} jobs."), \
            w[["name", "cooperative", "zone", "rating_avg", "jobs_done"]]
    return "Unknown question.", pd.DataFrame()

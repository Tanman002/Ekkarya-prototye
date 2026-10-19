"""e-Shram (National Database of Unorganised Workers) connector.

The functions below follow the shape of the aggregator integration the Ministry of
Labour & Employment requires under the Code on Social Security (worker lookup by
UAN, scheme status, and periodic submission of engaged-worker data).

MODE = "sandbox": the prototype runs against a simulated e-Shram registry table
(`eshram_registry`) built on that contract. MODE = "live" is where production
credentials and the NDUW API endpoint plug in — only this file changes.
"""
import json
import random
import re
import time

from core import db
from core.config import APP_NAME_LATIN, COOP_BY_ID, now

MODE = "sandbox"
SCHEMES = {
    "pmsby": "PM Suraksha Bima Yojana (accident cover)",
    "pmjjby": "PM Jeevan Jyoti Bima Yojana (life cover)",
    "pmsym": "PM Shram Yogi Maan-dhan (pension)",
}


def normalize_uan(uan: str) -> str:
    return re.sub(r"\D", "", uan or "")


def mask_uan(uan: str) -> str:
    u = normalize_uan(uan)
    return f"XXXX XXXX {u[-4:]}" if len(u) >= 4 else "—"


def verify_uan(uan: str) -> dict:
    """Look up a worker by 12-digit UAN. Returns status VERIFIED / NOT_FOUND / INVALID."""
    time.sleep(1.1)  # network round trip
    u = normalize_uan(uan)
    if len(u) != 12:
        return {"status": "INVALID", "message": "UAN must be 12 digits"}
    r = db.one("select * from eshram_registry where uan=?", (u,))
    if not r:
        return {"status": "NOT_FOUND", "uan": u}
    return {
        "status": "VERIFIED", "uan": u, "name": r["name"], "occupation": r["occupation"],
        "state": r["state"], "district": r["district"], "registered_on": r["registered_on"],
        "mobile": r["mobile_masked"], "bank_seeded": bool(r["bank_seeded"]),
        "schemes": {k: r[k] for k in SCHEMES},
    }


def schemes_for(uan: str) -> dict:
    r = db.one("select pmsby, pmjjby, pmsym from eshram_registry where uan=?", (normalize_uan(uan),))
    return r or {}


def engagement_records(coop_id: str, days: int = 30):
    """Build the engaged-worker payload for a cooperative for the last `days` days."""
    df = db.q("""select w.worker_id, w.name, w.eshram_uan, count(p.payment_id) as jobs,
                        count(distinct substr(p.paid_at,1,10)) as engagement_days,
                        coalesce(sum(p.worker_net),0) as net_earnings
                 from workers w left join payments p on p.worker_id=w.worker_id
                      and p.paid_at >= date('now', ?)
                 where w.coop_id=? and w.kyc_status='verified'
                 group by w.worker_id""", (f"-{days} days", coop_id))
    df["platform"] = APP_NAME_LATIN
    df["aggregator_type"] = "Cooperative platform"
    df["cooperative"] = COOP_BY_ID[coop_id]["name"]
    df["uan"] = df.eshram_uan.fillna("")
    return df


def submit_engagement(coop_id: str, records) -> dict:
    """Submit engaged-worker data; records without a UAN are returned as rejected."""
    time.sleep(1.4)
    ok = records[records.uan.str.len() == 12]
    ref = f"ESH-AGG-{now():%Y%m%d}-{random.randint(100000, 999999)}"
    db.execute("insert into eshram_sync(coop_id,records,accepted,reference,period,synced_at) values(?,?,?,?,?,?)",
               (coop_id, len(records), len(ok), ref, "last 30 days", now().isoformat(timespec="seconds")))
    return {"reference": ref, "submitted": len(records), "accepted": len(ok),
            "rejected_no_uan": len(records) - len(ok), "received_at": now().strftime("%d %b %Y, %I:%M %p")}


def last_sync(coop_id: str | None = None):
    if coop_id:
        return db.one("select * from eshram_sync where coop_id=? order by sync_id desc limit 1", (coop_id,))
    return db.one("select * from eshram_sync order by sync_id desc limit 1")


def payload_preview(records, n=3) -> str:
    sample = records.head(n)
    return json.dumps({"aggregator": APP_NAME_LATIN, "period_days": 30, "records": [
        {"uan": r.uan or None, "engagement_days": int(r.engagement_days), "jobs": int(r.jobs),
         "earnings_inr": round(float(r.net_earnings), 2)} for r in sample.itertuples()]}, indent=2)

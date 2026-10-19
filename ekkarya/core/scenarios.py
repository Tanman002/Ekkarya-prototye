"""One-click demo scenarios (F20). Each resets the relevant state so the demo is repeatable."""
from core import db
from core.config import DEMO_CUSTOMER, DEMO_WORKER, EMERGENCY_RADII, SIM_EMERG_ACCEPT_S
from datetime import timedelta

from core.config import now
from core.engine import ts
from core.matching import haversine

SCENARIOS = {
    "normal": ("Normal booking", "Customer books Electrical → Fan repair → Now. Ramesh (Worker tab) gets the offer."),
    "emergency": ("Emergency booking", "Customer taps Emergency → Plumbing. Broadcast to nearby plumbers; "
                  f"Ramesh has {SIM_EMERG_ACCEPT_S}s before a simulated worker accepts."),
    "no_worker": ("No worker found", "All carpenters are offline. Customer books Carpentry to see the fallback."),
    "spike": ("Monsoon demand spike", "Heavy-rain alert: plumbing & electrical forecast ×1.8 for 3 days in "
              "Mira–Bhayandar and Thane. See Forecast & Allocation."),
    "complaint": ("Complaint escalation", "A price-dispute complaint is escalated from the cooperative to the federation."),
}


def _clear_live():
    db.execute("update bookings set status='cancelled' where source='app' and status in "
               "('matching','en_route','in_progress','completed','paid')")
    db.execute("update job_requests set response='expired' where response='pending'")
    db.execute("update workers set is_online=1 where worker_id=?", (DEMO_WORKER,))


def _customer_loc():
    c = db.one("select lat, lon from customers where customer_id=?", (DEMO_CUSTOMER,))
    return c["lat"], c["lon"]


def _nearby_with_skill(service_id, km):
    lat, lon = _customer_loc()
    w = db.q("""select w.worker_id, w.lat, w.lon from workers w join worker_skills s on s.worker_id=w.worker_id
                where s.service_id=? and w.kyc_status='verified' and w.worker_id<>?""", (service_id, DEMO_WORKER))
    w["d"] = haversine(lat, lon, w.lat.values, w.lon.values)
    return w, w[w.d <= km]


def run(key: str) -> str:
    db.reset_db()  # every scenario starts from the clean seed state
    if key == "normal":
        # make Ramesh the best electrician near Priya: other nearby electricians go offline
        _, near = _nearby_with_skill("S2", 8)
        db.executemany("update workers set is_online=0 where worker_id=?", [(w,) for w in near.worker_id])
        db.execute("update workers set last_assigned_at=? where worker_id=?",
                   ((now() - timedelta(hours=20)).isoformat(timespec="seconds"), DEMO_WORKER))
    elif key == "emergency":
        allw, near = _nearby_with_skill("S1", EMERGENCY_RADII[0])
        near = near.sort_values("d")
        on = set(near.worker_id.head(2))
        db.executemany("update workers set is_online=? where worker_id=?",
                       [(1 if w in on else 0, w) for w in near.worker_id])
    elif key == "no_worker":
        db.execute("update workers set is_online=0 where worker_id in "
                   "(select worker_id from worker_skills where service_id='S5')")
    elif key == "spike":
        db.set_setting("spike", "1")
    elif key == "complaint":
        b = db.one("""select b.booking_id, b.coop_id, b.worker_id from bookings b where b.coop_id='C1'
                      and b.status='rated' order by b.booking_id desc limit 1""")
        db.execute("""insert into complaints(booking_id,coop_id,worker_id,raised_by,category,detail,status,escalated,
                      resolution,created_at) values(?,?,?,?,?,?,?,?,?,?)""",
                   (b["booking_id"], b["coop_id"], b["worker_id"], "customer", "Price dispute",
                    "Charged for an extra part that was not replaced. Customer wants a refund of ₹250.",
                    "escalated", 1, "Cooperative could not resolve within 48 h — escalated to federation.", ts()))
    return SCENARIOS[key][1]

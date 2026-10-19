"""Booking lifecycle and live simulation.

Status machine:
  matching → en_route → in_progress → completed → paid → rated
  exits: cancelled, no_worker_found

The live demo worker (is_demo = 1) acts through the Worker app. Every other worker
is simulated: tick() — called by the customer's tracking screen every ~2 s — makes
them accept, travel and finish on the timings in config.
"""
import json
import random
from datetime import datetime

import pandas as pd

from core import db, matching, pricing
from core.config import (DEMO_OFFER_TIMEOUT_S, EMERG_ROUND_S, EMERGENCY_RADII, SIM_ACCEPT_S,
                         SIM_EMERG_ACCEPT_S, SIM_TRAVEL_S, SIM_WORK_S, WELFARE_PREMIUM, now)

ACTIVE = ("matching", "en_route", "in_progress", "completed")


def ts() -> str:
    return now().isoformat(timespec="seconds")


def _age(s) -> float:
    if not s:
        return 0.0
    return (now() - datetime.fromisoformat(s)).total_seconds()


def get(bid) -> dict | None:
    return db.one("select * from bookings where booking_id=?", (int(bid),))


def worker(wid) -> dict | None:
    return db.one("select * from workers where worker_id=?", (wid,)) if wid else None


# ------------------------------------------------------------------ create
def create_booking(customer_id, service_id, issue_id, btype, slot_date, block, address, lat, lon,
                   zone_id, coop_id, description="", source="app") -> int:
    it = pricing.issue(issue_id)
    efee = it["emergency_fee"] if btype == "emergency" else 0
    bid = db.execute(
        """insert into bookings(customer_id,service_id,issue_id,btype,block,slot_date,address,lat,lon,
           zone_id,coop_id,status,created_at,start_otp,price,emergency_fee,extras,description,
           radius_km,round_started_at,round_no,source)
           values(?,?,?,?,?,?,?,?,?,?,?,'matching',?,?,?,?,'[]',?,?,?,0,?)""",
        (customer_id, service_id, issue_id, btype, block, slot_date, address, lat, lon, zone_id, coop_id,
         ts(), f"{random.randint(1000, 9999)}", it["base_price"], efee, description,
         EMERGENCY_RADII[0] if btype == "emergency" else None, ts(), source))
    b = get(bid)
    if btype == "emergency":
        _broadcast(b, 0)
    else:
        _offer_next(b)
    return bid


def _requested_ids(bid) -> set:
    return set(db.q("select worker_id from job_requests where booking_id=?", (bid,)).worker_id)


def _insert_request(bid, row):
    comp = matching.components_json(row)
    db.execute("insert into job_requests(booking_id,worker_id,sent_at,score,distance_km,components) "
               "values(?,?,?,?,?,?)", (bid, row["worker_id"], ts(), comp["score"], comp["distance_km"],
                                       json.dumps(comp)))


def _offer_next(b):
    cands = matching.candidates(b)
    done = _requested_ids(b["booking_id"])
    cands = cands[~cands.worker_id.isin(done)] if not cands.empty else cands
    if cands.empty:
        db.execute("update bookings set status='no_worker_found' where booking_id=?", (b["booking_id"],))
        return
    _insert_request(b["booking_id"], cands.iloc[0])


def _broadcast(b, round_no):
    radius = EMERGENCY_RADII[round_no]
    cands = matching.candidates(b, emergency=True, max_km=radius)
    done = _requested_ids(b["booking_id"])
    if not cands.empty:
        cands = cands[~cands.worker_id.isin(done)]
        for _, row in cands.iterrows():
            _insert_request(b["booking_id"], row)
    db.execute("update bookings set radius_km=?, round_no=?, round_started_at=? where booking_id=?",
               (radius, round_no, ts(), b["booking_id"]))


def requests(bid) -> pd.DataFrame:
    return db.q("""select r.*, w.name, w.is_demo from job_requests r join workers w on w.worker_id=r.worker_id
                   where r.booking_id=? order by r.score desc""", (bid,))


# ------------------------------------------------------------------ worker actions
def accept(bid, wid) -> bool:
    b = get(bid)
    if not b or b["status"] != "matching":
        return False
    db.execute("update bookings set status='en_route', worker_id=?, matched_at=?, accepted_at=? "
               "where booking_id=? and status='matching'", (wid, ts(), ts(), bid))
    b = get(bid)
    if b["worker_id"] != wid:
        return False
    db.execute("update job_requests set response='accepted', responded_at=? where booking_id=? and worker_id=?",
               (ts(), bid, wid))
    db.execute("update job_requests set response='taken', responded_at=? where booking_id=? and response='pending'",
               (ts(), bid))
    db.execute("update workers set last_assigned_at=? where worker_id=?", (ts(), wid))
    return True


def decline(bid, wid):
    db.execute("update job_requests set response='declined', responded_at=? where booking_id=? and worker_id=?",
               (ts(), bid, wid))
    b = get(bid)
    if b and b["status"] == "matching" and b["btype"] != "emergency":
        _offer_next(b)


def start_job(bid, otp: str) -> bool:
    b = get(bid)
    if b and str(otp).strip() == str(b["start_otp"]):
        db.execute("update bookings set status='in_progress', started_at=? where booking_id=?", (ts(), bid))
        return True
    return False


def complete_job(bid):
    db.execute("update bookings set status='completed', completed_at=? where booking_id=?", (ts(), bid))


def add_extra(bid, issue_id):
    b = get(bid)
    it = pricing.issue(issue_id)
    ex = json.loads(b["extras"] or "[]")
    ex.append({"issue_id": issue_id, "name": it["name_en"], "price": float(it["base_price"]), "approved": False})
    db.execute("update bookings set extras=? where booking_id=?", (json.dumps(ex), bid))


def set_extra(bid, idx, approved: bool):
    b = get(bid)
    ex = json.loads(b["extras"] or "[]")
    if approved:
        ex[idx]["approved"] = True
    else:
        ex.pop(idx)
    db.execute("update bookings set extras=? where booking_id=?", (json.dumps(ex), bid))


def cancel(bid):
    db.execute("update bookings set status='cancelled' where booking_id=? and status in ('matching','en_route')", (bid,))
    db.execute("update job_requests set response='expired' where booking_id=? and response='pending'", (bid,))


# ------------------------------------------------------------------ simulation
def tick(bid) -> dict | None:
    b = get(bid)
    if not b:
        return None
    st = b["status"]
    if st == "matching":
        reqs = requests(bid)
        pend = reqs[reqs.response == "pending"]
        if b["btype"] == "emergency":
            sim = pend[(pend.is_demo == 0) & (pend.sent_at.map(_age) >= SIM_EMERG_ACCEPT_S)]
            if not sim.empty:
                accept(bid, sim.iloc[0].worker_id)
            elif _age(b["round_started_at"]) >= EMERG_ROUND_S:
                nxt = int(b["round_no"]) + 1
                if nxt < len(EMERGENCY_RADII):
                    _broadcast(b, nxt)
                elif pend.empty or _age(b["round_started_at"]) >= EMERG_ROUND_S * 2:
                    db.execute("update job_requests set response='expired' where booking_id=? and response='pending'",
                               (bid,))
                    db.execute("update bookings set status='no_worker_found' where booking_id=?", (bid,))
            elif reqs.empty and int(b["round_no"]) == len(EMERGENCY_RADII) - 1:
                db.execute("update bookings set status='no_worker_found' where booking_id=?", (bid,))
        else:
            if pend.empty:
                _offer_next(b)
            for _, r in pend.iterrows():
                age = _age(r.sent_at)
                if r.is_demo == 0 and age >= SIM_ACCEPT_S:
                    accept(bid, r.worker_id)
                elif r.is_demo == 1 and age >= DEMO_OFFER_TIMEOUT_S:
                    db.execute("update job_requests set response='expired', responded_at=? where request_id=?",
                               (ts(), int(r.request_id)))
                    _offer_next(get(bid))
    elif b["worker_id"]:
        w = worker(b["worker_id"])
        if w and not w["is_demo"]:
            if st == "en_route" and _age(b["accepted_at"]) >= SIM_TRAVEL_S:
                db.execute("update bookings set status='in_progress', started_at=? where booking_id=?", (ts(), bid))
            elif st == "in_progress" and _age(b["started_at"]) >= SIM_WORK_S:
                complete_job(bid)
    return get(bid)


# ------------------------------------------------------------------ payment & feedback
def pay(bid, method="UPI") -> dict | None:
    b = get(bid)
    w = worker(b["worker_id"])
    if db.get_setting("pay_fail_next", "0") == "1":
        db.set_setting("pay_fail_next", "0")
        return None
    bl = pricing.bill(b, bool(w["insured"]))
    inv = pricing.invoice_no(b["coop_id"], bid)
    db.execute("""insert into payments(booking_id,coop_id,worker_id,gross,coop_charge,gst,welfare,worker_net,total,
                  method,status,paid_at,invoice_no) values(?,?,?,?,?,?,?,?,?,?,'success',?,?)""",
               (bid, b["coop_id"], b["worker_id"], bl["gross"], bl["coop_charge"], bl["gst"], bl["welfare"],
                bl["worker_net"], bl["total"], method, ts(), inv))
    db.execute("update bookings set status='paid' where booking_id=?", (bid,))
    db.execute("update workers set jobs_done=jobs_done+1 where worker_id=?", (b["worker_id"],))
    if w["insured"]:
        db.execute("update welfare set total_premium_paid=total_premium_paid+? where worker_id=?",
                   (WELFARE_PREMIUM, b["worker_id"]))
    return payment(bid)


def payment(bid) -> dict | None:
    return db.one("select * from payments where booking_id=? order by payment_id desc", (bid,))


def rate(bid, from_role, to_id, stars, tags=(), comment=""):
    db.execute("insert into ratings(booking_id,from_role,to_id,stars,tags,comment,created_at) values(?,?,?,?,?,?,?)",
               (bid, from_role, to_id, int(stars), json.dumps(list(tags)), comment, ts()))
    if from_role == "customer":
        w = worker(to_id)
        n = max(int(w["jobs_done"]), 1)
        new = round((w["rating_avg"] * (n - 1) + stars) / n, 2)
        db.execute("update workers set rating_avg=? where worker_id=?", (new, to_id))
        db.execute("update bookings set status='rated' where booking_id=?", (bid,))


def raise_complaint(bid, raised_by, category, detail):
    b = get(bid)
    db.execute("""insert into complaints(booking_id,coop_id,worker_id,raised_by,category,detail,status,escalated,created_at)
                  values(?,?,?,?,?,?,'open',0,?)""", (bid, b["coop_id"], b["worker_id"], raised_by, category, detail, ts()))


def active_for_customer(cid) -> dict | None:
    return db.one(f"select * from bookings where customer_id=? and status in {ACTIVE + ('paid',)} "
                  "order by booking_id desc limit 1", (cid,))


def active_for_worker(wid) -> dict | None:
    return db.one("select * from bookings where worker_id=? and status in ('en_route','in_progress','completed','paid') "
                  "and source='app' order by booking_id desc limit 1", (wid,))


def pending_offers(wid) -> pd.DataFrame:
    return db.q("""select r.request_id, r.sent_at, r.distance_km, r.score, b.*
                   from job_requests r join bookings b on b.booking_id=r.booking_id
                   where r.worker_id=? and r.response='pending' and b.status='matching'
                   order by b.btype='emergency' desc, r.sent_at""", (wid,))

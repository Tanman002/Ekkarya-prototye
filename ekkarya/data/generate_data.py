"""Synthetic data generator for the Ekकार्य prototype (seeded, reproducible).

Run directly to rebuild:  python -m data.generate_data
The app also calls build() automatically on first start and once per day, so the
last six months of history always end "yesterday".

Everything here is synthetic. Demand follows explainable rules (monsoon plumbing,
summer AC, pre-festival cleaning) so the forecasting model has real patterns to learn.
"""
import json
import os
import random
import sqlite3
import sys
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import (  # noqa: E402
    COOP_BY_ID, COOP_CHARGE_PCT, COOPS, DEMO_CUSTOMER, DEMO_NEW_UAN, DEMO_WORKER,
    FESTIVAL_WINDOW_DAYS, FESTIVALS, GROUP_ACCIDENT_COVER, GST_RATE, ISSUES, MONSOON,
    SERVICE_BY_ID, SERVICES, SHIFT_BLOCKS, TIME_BLOCKS, WELFARE_PREMIUM, ZONE_BY_ID, ZONES,
    now, today,
)

HISTORY_DAYS = 176
DETAIL_DAYS = 30
N_WORKERS = 340
N_CUSTOMERS = 800
DEMAND_SCALE = 0.7

FIRST_M = ["Ramesh", "Suresh", "Mahesh", "Ganesh", "Santosh", "Prakash", "Vijay", "Anil", "Sunil", "Raju",
           "Deepak", "Manoj", "Sachin", "Nitin", "Rahul", "Amit", "Imran", "Salim", "Arif", "Joseph",
           "Rajesh", "Dinesh", "Kiran", "Vikas", "Sandeep", "Ajay", "Mangesh", "Tukaram", "Balu", "Shankar"]
FIRST_F = ["Sunita", "Anita", "Rekha", "Lata", "Kavita", "Meena", "Savita", "Asha", "Shabana", "Mary",
           "Pooja", "Priya", "Jyoti", "Vaishali", "Manisha", "Sangeeta", "Reshma", "Nirmala", "Usha", "Kalpana"]
LAST = ["Patil", "Jadhav", "Pawar", "More", "Shinde", "Gaikwad", "Kamble", "Yadav", "Gupta", "Sharma",
        "Singh", "Khan", "Shaikh", "Ansari", "D'Souza", "Naik", "Salvi", "Chavan", "Mishra", "Pandey",
        "Kadam", "Sawant", "Thakur", "Mhatre", "Bhoir", "Tiwari", "Chauhan", "Parab", "Rane", "Mane"]
SOCIETIES = ["Shanti Nagar", "Poonam Sagar", "Hatkesh Society", "Kanakia Park", "Sai Krupa CHS", "Om Shivam CHS",
             "Sunrise Heights", "Gokul Dham", "Lodha Complex", "Vasant Vihar", "Hiranandani Estate", "Green Acres",
             "Ekta Nagar", "Silver Park", "Ram Nagar", "Laxmi Niwas", "Palm Court", "Sky Heights"]


def _season(key, d, rain_days):
    m = d.month
    mult = 1.0
    ms, md, me, mde = MONSOON
    monsoon = (m, d.day) >= (ms, md) and (m, d.day) <= (me, mde)
    fest = any(0 <= (f - d).days <= FESTIVAL_WINDOW_DAYS for _, f in FESTIVALS)
    if key == "ac":
        mult *= {1: .8, 2: 1.0, 3: 1.6, 4: 2.5, 5: 2.6, 6: 1.6, 7: .8, 8: .8, 9: .9, 10: 1.2, 11: .9, 12: .6}[m]
    if key == "plumbing" and monsoon:
        mult *= 1.8
    if key == "electrical":
        if monsoon:
            mult *= 1.25
        if fest:
            mult *= 1.6
    if key == "cleaning" and fest:
        mult *= 1.6
    if key == "appliance" and monsoon:
        mult *= 1.1
    wk = d.weekday() >= 5
    if wk:
        mult *= 1.3 if key in ("cleaning", "carpentry") else 1.05
    if d in rain_days and key in ("plumbing", "electrical"):
        mult *= 1.5
    return mult


def _haversine(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp, dl = p2 - p1, np.radians(lon2 - lon1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


DDL = """
create table settings(key text primary key, value text);
create table bookings(
  booking_id integer primary key autoincrement,
  customer_id text, service_id text, issue_id text, btype text, block text, slot_date text,
  address text, lat real, lon real, zone_id text, coop_id text,
  status text, worker_id text, created_at text, matched_at text, accepted_at text,
  started_at text, completed_at text, start_otp text, price real, emergency_fee real,
  extras text default '[]', description text, radius_km real, round_started_at text,
  round_no integer default 0, source text default 'app');
create table job_requests(
  request_id integer primary key autoincrement, booking_id integer, worker_id text,
  sent_at text, response text default 'pending', responded_at text,
  score real, distance_km real, components text);
create table payments(
  payment_id integer primary key autoincrement, booking_id integer, coop_id text, worker_id text,
  gross real, coop_charge real, gst real, welfare real, worker_net real, total real,
  method text, status text, paid_at text, invoice_no text);
create table ratings(
  rating_id integer primary key autoincrement, booking_id integer, from_role text, to_id text,
  stars integer, tags text, comment text, created_at text);
create table complaints(
  complaint_id integer primary key autoincrement, booking_id integer, coop_id text, worker_id text,
  raised_by text, category text, detail text, status text, escalated integer default 0,
  resolution text, created_at text);
create table notifications(
  notif_id integer primary key autoincrement, worker_id text, message text, created_at text,
  is_read integer default 0);
create table eshram_sync(
  sync_id integer primary key autoincrement, coop_id text, records integer, accepted integer,
  reference text, period text, synced_at text);
"""


def build(path):
    rng = np.random.default_rng(42)
    random.seed(42)
    anchor = today()
    t_now = now()
    if os.path.exists(path):
        os.remove(path)
    con = sqlite3.connect(path)
    con.executescript(DDL)
    con.execute("insert into settings values('anchor', ?)", (anchor.isoformat(),))
    con.execute("insert into settings values('spike', '0')")
    con.execute("insert into settings values('pay_fail_next', '0')")

    # ---------------- reference tables
    pd.DataFrame([{"federation_id": "F1", "name": "Thane–Mumbai Suburban Service Cooperative Federation",
                   "state": "Maharashtra", "district": "Thane / Mumbai Suburban"}]).to_sql("federations", con, index=False)
    pd.DataFrame([{**c, "federation_id": "F1"} for c in COOPS]).to_sql("cooperatives", con, index=False)
    pd.DataFrame(ZONES).to_sql("zones", con, index=False)
    pd.DataFrame([{k: s[k] for k in ("service_id", "key", "icon", "emergency_fee", "occupation")} for s in SERVICES]
                 ).to_sql("services", con, index=False)
    issues = pd.DataFrame(ISSUES, columns=["issue_id", "service_id", "name_en", "name_hi", "name_mr",
                                           "base_price", "est_minutes", "urgent"])
    issues["emergency_fee"] = issues.service_id.map(lambda s: SERVICE_BY_ID[s]["emergency_fee"])
    issues.to_sql("issues", con, index=False)

    # ---------------- workers
    zone_ids = [z["zone_id"] for z in ZONES]
    zw = np.array([z["weight"] for z in ZONES]); zw = zw / zw.sum()
    sids = [s["service_id"] for s in SERVICES]
    sw = np.array([s["base_daily"] for s in SERVICES], float); sw = sw / sw.sum()
    workers, skills = [], []
    uan_base = 400100200300
    for i in range(N_WORKERS):
        wid = f"W{i + 1:04d}"
        female = rng.random() < 0.28
        name = f"{random.choice(FIRST_F if female else FIRST_M)} {random.choice(LAST)}"
        z = ZONE_BY_ID[rng.choice(zone_ids, p=zw)]
        primary = rng.choice(sids, p=sw)
        if female and rng.random() < 0.7:
            primary = "S4"
        verified = rng.random() < 0.92
        certified = verified and rng.random() < 0.62
        rating = float(np.clip(rng.normal(4.3, 0.35), 3.3, 4.95))
        insured = verified and rng.random() < 0.72
        has_uan = rng.random() < (0.8 if verified else 0.5)
        workers.append(dict(
            worker_id=wid, coop_id=z["coop_id"], name=name, phone=f"9{rng.integers(100000000, 999999999)}",
            language=rng.choice(["mr", "hi", "en"], p=[.45, .45, .10]), zone_id=z["zone_id"],
            lat=z["lat"] + rng.normal(0, 0.008), lon=z["lon"] + rng.normal(0, 0.008),
            radius_km=int(rng.choice([5, 6, 8, 10])),
            kyc_status="verified" if verified else "pending",
            cert_status="certified" if certified else ("pending" if (not verified and rng.random() < .5) else "none"),
            id_doc="Aadhaar e-KYC (XXXX-XXXX-%04d)" % rng.integers(1000, 9999),
            is_online=int(verified and rng.random() < 0.62), rating_avg=round(rating, 2),
            jobs_done=int(rng.integers(40, 650)) if verified else 0, last_assigned_at=None,
            shift=rng.choice(list(SHIFT_BLOCKS), p=[.3, .35, .35]),
            eshram_uan=str(uan_base + i * 7) if has_uan else None, eshram_linked=int(has_uan),
            insured=int(insured),
            joined_on=(anchor - timedelta(days=int(rng.integers(30, 900) if verified else rng.integers(0, 10)))).isoformat(),
            is_demo=0, gender="F" if female else "M", years_exp=int(rng.integers(1, 18))))
        skills.append(dict(worker_id=wid, service_id=primary, years_exp=workers[-1]["years_exp"],
                           certified=int(certified)))
        if rng.random() < 0.3:
            second = rng.choice([s for s in sids if s != primary])
            skills.append(dict(worker_id=wid, service_id=second, years_exp=max(1, workers[-1]["years_exp"] - 2),
                               certified=0))

    # demo worker: Ramesh, electrician + plumber, Mira Road East
    d = workers[0]
    d.update(name="Ramesh Patil", phone="9867044556", language="mr", zone_id="Z01", coop_id="C1",
             lat=19.2795, lon=72.8660, radius_km=8, kyc_status="verified", cert_status="certified",
             is_online=1, rating_avg=4.72, jobs_done=312, shift="full", eshram_uan="400100200300",
             eshram_linked=1, insured=1, is_demo=1, gender="M", years_exp=9,
             joined_on=(anchor - timedelta(days=410)).isoformat())
    skills = [s for s in skills if s["worker_id"] != DEMO_WORKER]
    skills += [dict(worker_id=DEMO_WORKER, service_id="S2", years_exp=9, certified=1),
               dict(worker_id=DEMO_WORKER, service_id="S1", years_exp=6, certified=0)]
    wdf = pd.DataFrame(workers)
    sdf = pd.DataFrame(skills)

    # ---------------- customers
    customers = []
    for i in range(N_CUSTOMERS):
        z = ZONE_BY_ID[rng.choice(zone_ids, p=zw)]
        female = rng.random() < .5
        customers.append(dict(
            customer_id=f"CU{i + 1:04d}", name=f"{random.choice(FIRST_F if female else FIRST_M)} {random.choice(LAST)}",
            phone=f"9{rng.integers(100000000, 999999999)}", language=rng.choice(["en", "hi", "mr"], p=[.4, .35, .25]),
            ctype=rng.choice(["household", "rwa", "business"], p=[.8, .15, .05]),
            address=f"Flat {rng.integers(101, 1504)}, {random.choice(SOCIETIES)}, {z['name']}",
            lat=z["lat"] + rng.normal(0, 0.007), lon=z["lon"] + rng.normal(0, 0.007), zone_id=z["zone_id"]))
    customers[0].update(name="Priya Sharma", phone="9820011223", language="en", ctype="household",
                        address="Flat 704, Shanti Nagar Sector 5, Mira Road East", lat=19.2860, lon=72.8712,
                        zone_id="Z01")
    cdf = pd.DataFrame(customers)

    # ---------------- demand history (aggregated)
    start = anchor - timedelta(days=HISTORY_DAYS)
    dates = [start + timedelta(days=i) for i in range(HISTORY_DAYS)]
    monsoon_dates = [x for x in dates if x.month in (6, 7, 8, 9)]
    rain_days = set(random.sample(monsoon_dates, min(14, len(monsoon_dates))))
    rows = []
    for di, dt in enumerate(dates):
        trend = 1 + 0.25 * di / HISTORY_DAYS
        for z in ZONES:
            for s in SERVICES:
                lam_day = DEMAND_SCALE * s["base_daily"] * z["weight"] * _season(s["key"], dt, rain_days) * trend
                for b in TIME_BLOCKS:
                    rows.append((dt.isoformat(), b["id"], z["zone_id"], s["service_id"],
                                 int(rng.poisson(lam_day * b["share"]))))
    hist = pd.DataFrame(rows, columns=["date", "block", "zone_id", "service_id", "bookings"])
    hist.to_sql("demand_history", con, index=False)

    # ---------------- individual bookings for the last DETAIL_DAYS (+ today so far)
    verified = wdf[wdf.kyc_status == "verified"]
    vskills = sdf[sdf.worker_id.isin(verified.worker_id)]
    pool = {}
    for (zid, sid), _ in hist.groupby(["zone_id", "service_id"]):
        zone_w = verified[verified.zone_id == zid].worker_id
        cand = vskills[(vskills.service_id == sid) & (vskills.worker_id.isin(zone_w))].worker_id.tolist()
        if len(cand) < 2:
            coop_w = verified[verified.coop_id == ZONE_BY_ID[zid]["coop_id"]].worker_id
            cand += vskills[(vskills.service_id == sid) & (vskills.worker_id.isin(coop_w))].worker_id.tolist()
        if not cand:
            cand = vskills[vskills.service_id == sid].worker_id.tolist()
        pool[(zid, sid)] = cand
    cust_by_zone = cdf.groupby("zone_id").customer_id.apply(list).to_dict()
    cust_idx = cdf.set_index("customer_id")
    issue_by_svc = issues.groupby("service_id").issue_id.apply(list).to_dict()
    price = issues.set_index("issue_id").base_price.to_dict()
    wmap = wdf.set_index("worker_id")
    block_start = {b["id"]: b["start"] for b in TIME_BLOCKS}
    block_end = {b["id"]: b["end"] for b in TIME_BLOCKS}

    detail = hist[hist.date >= (anchor - timedelta(days=DETAIL_DAYS)).isoformat()].copy()
    # today so far: blocks that have already ended
    today_rows = []
    for z in ZONES:
        for s in SERVICES:
            lam_day = DEMAND_SCALE * s["base_daily"] * z["weight"] * _season(s["key"], anchor, rain_days) * 1.25
            for b in TIME_BLOCKS:
                frac = min(max((t_now.hour + t_now.minute / 60 - b["start"]) / (b["end"] - b["start"]), 0), 1)
                if frac > 0:
                    today_rows.append((anchor.isoformat(), b["id"], z["zone_id"], s["service_id"],
                                       int(rng.poisson(lam_day * b["share"] * frac))))
    detail = pd.concat([detail, pd.DataFrame(today_rows, columns=detail.columns)], ignore_index=True)

    bookings, payments, ratings, complaints = [], [], [], []
    bid = 0
    last_assigned = {}
    tags_pool = ["On time", "Clean work", "Polite", "Fair price", "Explained the problem"]
    for r in detail.itertuples(index=False):
        if r.bookings == 0:
            continue
        cands = pool[(r.zone_id, r.service_id)]
        for _ in range(r.bookings):
            bid += 1
            wid = random.choice(cands)
            cid = random.choice(cust_by_zone.get(r.zone_id, [DEMO_CUSTOMER]))
            c = cust_idx.loc[cid]
            iid = random.choice(issue_by_svc[r.service_id])
            emerg = rng.random() < (0.12 if r.service_id in ("S1", "S2") else 0.03)
            btype = "emergency" if emerg else ("scheduled" if rng.random() < .72 else "now")
            dt = datetime.fromisoformat(r.date)
            created = dt + timedelta(hours=block_start[r.block] - (0 if btype != "scheduled" else 20),
                                     minutes=int(rng.integers(0, 50)))
            acc = created + timedelta(minutes=int(rng.integers(1, 6)))
            started = max(acc, dt + timedelta(hours=block_start[r.block])) + timedelta(minutes=int(rng.integers(10, 50)))
            done = started + timedelta(minutes=int(rng.integers(30, 120)))
            if done.hour >= block_end[r.block] + 2:
                done = dt + timedelta(hours=block_end[r.block], minutes=int(rng.integers(0, 50)))
            efee = SERVICE_BY_ID[r.service_id]["emergency_fee"] if emerg else 0
            p = price[iid]
            rated = rng.random() < 0.8
            status = "rated" if rated else "paid"
            coop = ZONE_BY_ID[r.zone_id]["coop_id"]
            bookings.append((bid, cid, r.service_id, iid, btype, r.block, r.date, c.address, c.lat, c.lon,
                             r.zone_id, coop, status, wid, created.isoformat(), acc.isoformat(), acc.isoformat(),
                             started.isoformat(), done.isoformat(), f"{rng.integers(1000, 9999)}", p, efee,
                             "[]", "", None, None, 0, "app"))
            gross = p + efee
            cc = round(gross * COOP_CHARGE_PCT, 2)
            gst = round(cc * GST_RATE, 2)
            wel = WELFARE_PREMIUM if wmap.at[wid, "insured"] else 0
            ym = r.date[:7].replace("-", "")
            payments.append((bid, coop, wid, gross, cc, gst, wel, gross - cc - wel, gross + gst, "UPI", "success",
                             (done + timedelta(minutes=3)).isoformat(),
                             f"EK-{COOP_BY_ID[coop]['code']}-{ym}-{bid:06d}"))
            if rated:
                stars = int(np.clip(round(rng.normal(wmap.at[wid, "rating_avg"], 0.6)), 1, 5))
                tg = random.sample(tags_pool, k=int(rng.integers(0, 3))) if stars >= 4 else []
                ratings.append((bid, "customer", wid, stars, json.dumps(tg), "", (done + timedelta(minutes=5)).isoformat()))
                if stars <= 2 and rng.random() < 0.25:
                    cat = random.choice(["Work quality", "Late arrival", "Price dispute", "Behaviour"])
                    st_ = rng.choice(["resolved", "open", "escalated"], p=[.75, .18, .07])
                    complaints.append((bid, coop, wid, "customer", cat,
                                       {"Work quality": "Leak started again the next day.",
                                        "Late arrival": "Worker arrived much later than the slot.",
                                        "Price dispute": "Extra item was added without asking.",
                                        "Behaviour": "Worker was rude on the phone."}[cat],
                                       st_, int(st_ == "escalated"),
                                       "Re-visit done free of cost." if st_ == "resolved" else None,
                                       (done + timedelta(hours=2)).isoformat()))
            last_assigned[wid] = max(last_assigned.get(wid, ""), acc.isoformat())

    # active jobs right now (simulated workers only)
    busy = set()
    for _ in range(18):
        z = ZONE_BY_ID[rng.choice(zone_ids, p=zw)]
        sid = rng.choice(sids, p=sw)
        cands = [w for w in pool[(z["zone_id"], sid)] if w != DEMO_WORKER and w not in busy]
        if not cands:
            continue
        wid = random.choice(cands); busy.add(wid)
        cid = random.choice(cust_by_zone[z["zone_id"]]); c = cust_idx.loc[cid]
        iid = random.choice(issue_by_svc[sid])
        bid += 1
        acc = t_now - timedelta(minutes=int(rng.integers(5, 60)))
        st_ = rng.choice(["en_route", "in_progress"])
        bookings.append((bid, cid, sid, iid, "now", "morning", anchor.isoformat(), c.address, c.lat, c.lon,
                         z["zone_id"], z["coop_id"], st_, wid, (acc - timedelta(minutes=3)).isoformat(),
                         acc.isoformat(), acc.isoformat(),
                         (acc + timedelta(minutes=20)).isoformat() if st_ == "in_progress" else None, None,
                         f"{rng.integers(1000, 9999)}", price[iid], 0, "[]", "", None, None, 0, "seed"))
        last_assigned[wid] = acc.isoformat()

    con.executemany("insert into bookings values(" + ",".join("?" * 28) + ")", bookings)
    con.executemany("insert into payments(booking_id,coop_id,worker_id,gross,coop_charge,gst,welfare,worker_net,"
                    "total,method,status,paid_at,invoice_no) values(?,?,?,?,?,?,?,?,?,?,?,?,?)", payments)
    con.executemany("insert into ratings(booking_id,from_role,to_id,stars,tags,comment,created_at) "
                    "values(?,?,?,?,?,?,?)", ratings)
    con.executemany("insert into complaints(booking_id,coop_id,worker_id,raised_by,category,detail,status,"
                    "escalated,resolution,created_at) values(?,?,?,?,?,?,?,?,?,?)", complaints)

    # fairness input: hours since last job
    wdf["last_assigned_at"] = wdf.worker_id.map(last_assigned)
    wdf.loc[wdf.last_assigned_at.isna() & (wdf.kyc_status == "verified"), "last_assigned_at"] = \
        (t_now - timedelta(hours=30)).isoformat()
    wdf.loc[wdf.worker_id == DEMO_WORKER, "last_assigned_at"] = (t_now - timedelta(hours=20)).isoformat()
    wdf.to_sql("workers", con, index=False)
    sdf.to_sql("worker_skills", con, index=False)
    cdf.to_sql("customers", con, index=False)

    # ---------------- welfare
    wel = []
    for w in workers:
        wel.append(dict(worker_id=w["worker_id"], insurance_opted=w["insured"],
                        policy_no=f"EKGA/{w['worker_id']}/2026" if w["insured"] else None,
                        cover_amount=GROUP_ACCIDENT_COVER if w["insured"] else 0,
                        premium_per_job=WELFARE_PREMIUM if w["insured"] else 0,
                        total_premium_paid=(w["jobs_done"] * WELFARE_PREMIUM) if w["insured"] else 0))
    pd.DataFrame(wel).to_sql("welfare", con, index=False)

    # ---------------- e-Shram registry (sandbox copy of the NDUW records we are allowed to see)
    reg = []
    for w in workers:
        if not w["eshram_uan"]:
            continue
        primary = next(s["service_id"] for s in skills if s["worker_id"] == w["worker_id"])
        reg.append(dict(uan=w["eshram_uan"], name=w["name"], occupation=SERVICE_BY_ID[primary]["occupation"],
                        state="Maharashtra",
                        district="Thane" if ZONE_BY_ID[w["zone_id"]]["coop_id"] != "C2" else "Mumbai Suburban",
                        registered_on=(anchor - timedelta(days=int(rng.integers(120, 1500)))).isoformat(),
                        mobile_masked="XXXXXX" + w["phone"][-4:], bank_seeded=1,
                        pmsby="enrolled" if rng.random() < .7 else "eligible",
                        pmjjby="enrolled" if rng.random() < .35 else "eligible",
                        pmsym="enrolled" if rng.random() < .2 else "eligible"))
    extra_people = [("Sunita Jadhav", "Housekeeping Worker"), ("Mohan Kale", "Plumber"), ("Farhan Shaikh", "Electrician"),
                    ("Lalita Waghmare", "Housekeeping Worker"), ("Dattaram Bhosale", "Carpenter"),
                    ("Irfan Qureshi", "AC Technician"), ("Rohini Salunkhe", "Housekeeping Worker"),
                    ("Prashant Dhuri", "Appliance Repair Technician")]
    for k, (nm, occ) in enumerate(extra_people):
        reg.append(dict(uan=DEMO_NEW_UAN if k == 0 else str(100200300400 + k * 111), name=nm, occupation=occ,
                        state="Maharashtra", district="Thane",
                        registered_on=(anchor - timedelta(days=200 + k * 30)).isoformat(),
                        mobile_masked="XXXXXX%04d" % (3300 + k), bank_seeded=1,
                        pmsby="enrolled", pmjjby="eligible", pmsym="eligible"))
    pd.DataFrame(reg).to_sql("eshram_registry", con, index=False)

    for ddl in ("create index ix_b_status on bookings(status)", "create index ix_b_worker on bookings(worker_id)",
                "create index ix_b_cust on bookings(customer_id)", "create index ix_b_date on bookings(slot_date)",
                "create index ix_r_book on job_requests(booking_id)", "create index ix_p_book on payments(booking_id)",
                "create index ix_w on workers(worker_id)", "create index ix_h on demand_history(date)"):
        con.execute(ddl)
    con.commit()
    con.close()


if __name__ == "__main__":
    from core.config import SEED_DB_PATH
    import time
    t = time.time()
    build(SEED_DB_PATH)
    print(f"built {SEED_DB_PATH} in {time.time() - t:.1f}s")

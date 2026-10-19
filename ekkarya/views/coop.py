"""Cooperative manager dashboard (M1–M5) and the operations copilot (shared with the federation)."""
from datetime import timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from core import copilot, db, eshram_client
from core.config import (CHART_COLORS, COLORS, COOP_BY_ID, SERVICE_BY_ID, SERVICE_NAMES_EN, ZONE_BY_ID, ZONES,
                         today)
from core.pricing import inr
from core.ui import app_bar, badge, card, esc, kpi_row, style_fig
from views import analytics
from views.maps import markers_map

SVC_COLOR = {sid: CHART_COLORS[i] for i, sid in enumerate(SERVICE_NAMES_EN)}


def _coop():
    return st.session_state.user_id


def header(title):
    c = COOP_BY_ID[_coop()]
    app_bar(f"{c['name']} · {title}")


def eshram_status_chip():
    return badge("● e-Shram connected", "green")


# ------------------------------------------------------------------ M1
def dashboard():
    cid = _coop()
    header("Dashboard")
    t0 = today().isoformat()
    t30 = (today() - timedelta(days=29)).isoformat()
    w = db.q("select * from workers where coop_id=?", (cid,))
    v = w[w.kyc_status == "verified"]
    jobs_today = db.one("select count(*) n from bookings where coop_id=? and substr(created_at,1,10)=?", (cid, t0))["n"]
    rev_today = db.one("select coalesce(sum(gross),0) s from payments where coop_id=? and paid_at>=?", (cid, t0))["s"]
    rating = db.one("select avg(r.stars) a from ratings r join bookings b on b.booking_id=r.booking_id where "
                    "b.coop_id=? and r.from_role='customer' and r.created_at>=?", (cid, t30))["a"] or 0
    open_c = db.one("select count(*) n from complaints where coop_id=? and status='open'", (cid,))["n"]
    kpi_row([("Workers online", f"{int(v.is_online.sum())}", f"of {len(v)} verified members"),
             ("Jobs today", f"{jobs_today}", "all channels"),
             ("Revenue today", inr(rev_today), "gross service value"),
             ("Avg rating (30 d)", f"★ {rating:.2f}", "customer ratings"),
             ("Welfare coverage", f"{v.insured.mean() * 100:.0f}%", "insured members"),
             ("Open complaints", f"{open_c}", "needs action")])
    st.markdown(" ")
    c1, c2 = st.columns([3, 2])
    d = db.q("""select substr(created_at,1,10) day, service_id, count(*) n from bookings
                where coop_id=? and created_at>=? group by day, service_id""", (cid, t30))
    d["service"] = d.service_id.map(SERVICE_NAMES_EN)
    with c1:
        fig = px.bar(d, x="day", y="n", color="service", color_discrete_map={SERVICE_NAMES_EN[k]: v for k, v in SVC_COLOR.items()},
                     title="Jobs per day by service — last 30 days")
        fig.update_traces(marker_line_color="#FFFFFF", marker_line_width=1)
        st.plotly_chart(style_fig(fig, 340), use_container_width=True)
    with c2:
        live = db.q("""select b.lat, b.lon, b.status, b.service_id, w.name from bookings b join workers w on
                       w.worker_id=b.worker_id where b.coop_id=? and b.status in ('en_route','in_progress')""", (cid,))
        pts = [dict(lat=r.lat, lon=r.lon, color=COLORS["orange"], radius=8,
                    tooltip=f"{SERVICE_NAMES_EN[r.service_id]} · {r.name} · {r.status.replace('_', ' ')}")
               for r in live.itertuples()]
        pts += [dict(lat=r.lat, lon=r.lon, color=COLORS["green"], radius=4, opacity=.6, tooltip=f"{r.name} (online)")
                for r in v[v.is_online == 1].itertuples()]
        st.markdown("**Live jobs** <span class='ek-small'>· orange = active job, green = online worker</span>",
                    unsafe_allow_html=True)
        zc = [z for z in ZONES if z["coop_id"] == cid][0]
        markers_map(pts, [zc["lat"], zc["lon"]], zoom=12, height=300, key="m1map")

    st.markdown("#### e-Shram compliance")
    c1, c2 = st.columns([2, 3])
    last = eshram_client.last_sync(cid)
    with c1:
        card(f"<div style='display:flex;justify-content:space-between'><b>🇮🇳 e-Shram (NDUW)</b>{eshram_status_chip()}</div>"
             f"<div class='ek-big' style='color:#0B7A3E'>{v.eshram_linked.mean() * 100:.0f}%</div>"
             f"<div class='ek-small'>verified members linked by UAN · {int((1 - v.eshram_linked).sum())} to help register</div>"
             f"<div class='ek-small' style='margin-top:6px'>Last sync: "
             f"{(last['synced_at'][:16].replace('T', ' ') + ' · ref ' + last['reference']) if last else 'not yet this period'}</div>",
             "green")
    with c2:
        recs = eshram_client.engagement_records(cid)
        st.markdown(f"**Engaged-worker report** · last 30 days · {len(recs)} members")
        with st.expander("Preview payload"):
            st.code(eshram_client.payload_preview(recs), language="json")
        if st.button("⇪ Sync engaged-worker data to e-Shram", type="primary"):
            with st.spinner("Submitting to e-Shram…"):
                ack = eshram_client.submit_engagement(cid, recs)
            st.success(f"Acknowledged · ref **{ack['reference']}** · {ack['accepted']} accepted, "
                       f"{ack['rejected_no_uan']} returned (no UAN) · {ack['received_at']}")


# ------------------------------------------------------------------ M2
def verify():
    cid = _coop()
    header("Verification queue")
    p = db.q("select * from workers where coop_id=? and (kyc_status='pending' or cert_status='pending') "
             "order by joined_on desc", (cid,))
    if p.empty:
        card("✅ No pending verifications.", "green")
        return
    st.caption(f"{len(p)} members waiting · approve after checking ID, e-Shram and skills")
    for r in p.itertuples():
        sk = db.q("select service_id, years_exp from worker_skills where worker_id=?", (r.worker_id,))
        skills = ", ".join(f"{SERVICE_BY_ID[s.service_id]['icon']} {SERVICE_NAMES_EN[s.service_id]} ({s.years_exp}y)"
                           for s in sk.itertuples())
        with st.container(border=True):
            c1, c2 = st.columns([3, 2])
            c1.markdown(f"**{esc(r.name)}** · {r.worker_id} · {ZONE_BY_ID[r.zone_id]['name']}  \n"
                        f"<span class='ek-small'>Joined {r.joined_on} · +91 {r.phone} · {skills}</span>",
                        unsafe_allow_html=True)
            c1.markdown(
                (badge("KYC pending", "orange") if r.kyc_status == "pending" else badge("KYC verified", "green"))
                + (badge("e-Shram " + eshram_client.mask_uan(r.eshram_uan), "green") if r.eshram_linked
                   else badge("No e-Shram UAN", "grey"))
                + (badge("Certificate submitted", "orange") if r.cert_status == "pending" else "")
                + (badge("Opted for insurance", "green") if r.insured else ""), unsafe_allow_html=True)
            c1.markdown(f"<span class='ek-small'>ID: {esc(r.id_doc or 'uploaded')}</span>", unsafe_allow_html=True)
            if r.kyc_status == "pending":
                if c2.button("✔ Approve member", key=f"ap_{r.worker_id}", type="primary", use_container_width=True):
                    db.execute("update workers set kyc_status='verified', is_online=1 where worker_id=?", (r.worker_id,))
                    st.toast(f"{r.name} is now a verified member"); st.rerun()
                if c2.button("✖ Reject", key=f"rj_{r.worker_id}", use_container_width=True):
                    db.execute("update workers set kyc_status='rejected' where worker_id=?", (r.worker_id,)); st.rerun()
            if r.cert_status == "pending":
                if c2.button("🎓 Approve certificate", key=f"ce_{r.worker_id}", use_container_width=True):
                    db.execute("update workers set cert_status='certified' where worker_id=?", (r.worker_id,))
                    db.execute("update worker_skills set certified=1 where worker_id=?", (r.worker_id,)); st.rerun()


# ------------------------------------------------------------------ M3
def members():
    cid = _coop()
    header("Members")
    w = db.q("""select w.worker_id, w.name, w.zone_id, group_concat(s.service_id) skills, w.kyc_status, w.cert_status,
                w.rating_avg, w.jobs_done, w.insured, w.eshram_linked, w.is_online
                from workers w left join worker_skills s on s.worker_id=w.worker_id where w.coop_id=? group by w.worker_id""", (cid,))
    w["zone"] = w.zone_id.map(lambda z: ZONE_BY_ID[z]["name"])
    w["skills"] = w.skills.fillna("").map(lambda s: ", ".join(SERVICE_NAMES_EN[x] for x in s.split(",") if x))
    c1, c2, c3 = st.columns(3)
    q = c1.text_input("Search name")
    sk = c2.multiselect("Skill", list(SERVICE_NAMES_EN.values()))
    stt = c3.multiselect("Status", ["verified", "pending", "rejected"], default=["verified", "pending"])
    f = w[w.kyc_status.isin(stt)] if stt else w
    if q:
        f = f[f.name.str.contains(q, case=False)]
    if sk:
        f = f[f.skills.map(lambda s: any(x in s for x in sk))]
    st.caption(f"{len(f)} members")
    st.dataframe(f[["worker_id", "name", "zone", "skills", "kyc_status", "cert_status", "rating_avg", "jobs_done",
                    "insured", "eshram_linked", "is_online"]],
                 use_container_width=True, hide_index=True, height=480,
                 column_config={"rating_avg": st.column_config.NumberColumn("rating", format="★ %.2f"),
                                "insured": st.column_config.CheckboxColumn("insured"),
                                "eshram_linked": st.column_config.CheckboxColumn("e-Shram"),
                                "is_online": st.column_config.CheckboxColumn("online")})


# ------------------------------------------------------------------ M4
def complaints():
    cid = _coop()
    header("Complaints")
    c = db.q("""select c.*, w.name worker from complaints c left join workers w on w.worker_id=c.worker_id
                where c.coop_id=? order by c.status='resolved', c.complaint_id desc""", (cid,))
    kpi_row([("Open", str((c.status == "open").sum()), "awaiting action", "accent-o"),
             ("Escalated", str((c.status == "escalated").sum()), "with federation", "accent-o"),
             ("Resolved", str((c.status == "resolved").sum()), "all time")])
    st.markdown(" ")
    for r in c[c.status != "resolved"].itertuples():
        with st.container(border=True):
            st.markdown(f"**#{r.complaint_id} · {r.category}** · booking #{r.booking_id} · worker {esc(r.worker)}  \n"
                        f"{esc(r.detail)}  \n<span class='ek-small'>{r.created_at[:16].replace('T', ' ')}</span> "
                        + badge(r.status, "orange" if r.status == "open" else "red"), unsafe_allow_html=True)
            if r.status == "open":
                note = st.text_input("Resolution note", key=f"note_{r.complaint_id}")
                c1, c2 = st.columns(2)
                if c1.button("Resolve", key=f"res_{r.complaint_id}", type="primary", use_container_width=True):
                    db.execute("update complaints set status='resolved', resolution=? where complaint_id=?",
                               (note or "Resolved by cooperative", r.complaint_id)); st.rerun()
                if c2.button("Escalate to federation", key=f"esc_{r.complaint_id}", use_container_width=True):
                    db.execute("update complaints set status='escalated', escalated=1 where complaint_id=?",
                               (r.complaint_id,)); st.rerun()
    with st.expander("Resolved complaints"):
        st.dataframe(c[c.status == "resolved"][["complaint_id", "category", "worker", "detail", "resolution", "created_at"]],
                     hide_index=True, use_container_width=True)


# ------------------------------------------------------------------ M5
def rate_card():
    header("Rate card")
    st.caption("Prices are set by the cooperative and shown to customers before booking. No surge pricing.")
    df = db.q("select issue_id, service_id, name_en, base_price, emergency_fee, est_minutes from issues order by service_id, base_price")
    df["service"] = df.service_id.map(SERVICE_NAMES_EN)
    ed = st.data_editor(df[["issue_id", "service", "name_en", "base_price", "emergency_fee", "est_minutes"]],
                        disabled=["issue_id", "service", "name_en"], hide_index=True, use_container_width=True, height=560,
                        column_config={"base_price": st.column_config.NumberColumn("price (₹)", min_value=0, step=10),
                                       "emergency_fee": st.column_config.NumberColumn("emergency fee (₹)", min_value=0, step=10),
                                       "name_en": "issue", "est_minutes": "est. minutes"})
    if st.button("Save rate card", type="primary"):
        db.executemany("update issues set base_price=?, emergency_fee=?, est_minutes=? where issue_id=?",
                       [(float(r.base_price), float(r.emergency_fee), int(r.est_minutes), r.issue_id) for r in ed.itertuples()])
        st.success("Rate card updated — new bookings use these prices.")


# ------------------------------------------------------------------ copilot (F16)
def copilot_page():
    role = st.session_state.get("role")
    app_bar("Operations copilot" + (" · Federation" if role == "admin" else ""))
    st.caption("Ask a predefined operational question. Answers are computed from live data and the forecast; "
               "the evidence table is shown with every answer.")
    _, fc, spike = analytics.get()
    cols = st.columns(3)
    for i, (k, q) in enumerate(copilot.QUESTIONS.items()):
        if cols[i % 3].button(q, key=f"cq_{k}", use_container_width=True):
            st.session_state.cp_q = k
    k = st.session_state.get("cp_q")
    if k:
        with st.spinner("Analysing…"):
            text, ev = copilot.answer(k, fc)
        with st.chat_message("assistant", avatar="🤝"):
            st.markdown(f"**{copilot.QUESTIONS[k]}**")
            st.markdown(text)
            if spike:
                st.caption("⚠️ Heavy-rain alert is active — forecast includes the surge adjustment.")
            if not ev.empty:
                st.dataframe(ev, hide_index=True, use_container_width=True)

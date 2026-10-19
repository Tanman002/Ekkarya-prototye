"""Customer app (C1–C9): home, booking, tracking, payment, history, account."""
import io
import json
import time
from datetime import timedelta

import qrcode
import streamlit as st

from core import ai_assist, db, engine, invoice, pricing
from core.config import (COOP_BY_ID, EMERGENCY_RADII, SERVICE_BY_ID, SERVICES, TIME_BLOCKS, ZONE_BY_ID,
                         current_block, today)
from core.i18n import LANGS, block_label, issue_name, lang, svc, t
from core.matching import WEIGHTS
from core.nav import page
from core.pricing import inr
from core.ui import app_bar, avatar, badge, bar, bottom_nav, card, esc, timeline
from views.common import lang_widget, logout
from views.maps import point_map, route_map


# ------------------------------------------------------------------ helpers
def _me():
    return db.one("select * from customers where customer_id=?", (st.session_state.user_id,))


def _nav():
    bottom_nav([(page("c_home"), t("nav_home"), "🏠"), (page("c_track"), t("nav_track"), "📍"),
                (page("c_bookings"), t("nav_bookings"), "🧾"), (page("c_account"), t("nav_account"), "👤")])


def _start_booking(service_id=None, issue_id=None, btype="now", desc=""):
    st.session_state.book = {"service_id": service_id, "issue_id": issue_id, "btype": btype, "desc": desc}
    st.switch_page(page("c_book"))


def _current_bid():
    bid = st.session_state.get("current_booking")
    if bid:
        return bid
    a = engine.active_for_customer(st.session_state.user_id)
    if a:
        st.session_state.current_booking = a["booking_id"]
        return a["booking_id"]
    return None


def worker_trust_card(w, service_id):
    sk = db.one("select * from worker_skills where worker_id=? and service_id=?", (w["worker_id"], service_id)) or {}
    comp = db.one("select count(*) n from complaints where worker_id=? and status in ('open','escalated')",
                  (w["worker_id"],))["n"]
    badges = badge("✔ " + t("verified"), "green")
    if sk.get("certified"):
        badges += badge("🎓 " + t("certified"), "orange")
    if w["insured"]:
        badges += badge("🛡 " + t("insured"), "green")
    if w["eshram_linked"]:
        badges += badge("e-Shram " + t("linked"), "grey")
    card(f"""<div class="ek-row">{avatar(w['name'])}<div style="flex:1">
        <div style="font-weight:700;font-size:1.05rem">{esc(w['name'])}</div>
        <div class="ek-small">{esc(COOP_BY_ID[w['coop_id']]['name'])} · {t('member_id')} {w['worker_id']}</div>
        <div style="margin-top:4px">{badges}</div></div></div>
        <div class="ek-small" style="margin-top:8px">★ <b>{w['rating_avg']:.1f}</b> · {w['jobs_done']} {t('jobs_done')}
        · {sk.get('years_exp', w['years_exp'])} {t('years_exp')} · {t('open_complaints')}: {comp}</div>""")


def why_this_worker(bid, wid):
    r = db.one("select components from job_requests where booking_id=? and worker_id=?", (bid, wid))
    if not r or not r["components"]:
        return
    c = json.loads(r["components"])
    with st.expander("💡 " + t("why_worker")):
        rows = [("proximity", t("f_proximity"), f"{c['distance_km']:.1f} km"),
                ("rating", t("f_rating"), f"★ {c['rating_avg']:.1f}"),
                ("certification", t("f_cert"), t("yes") if c["certification"] else t("no")),
                ("fairness", t("f_fair"), t("hours_ago", h=f"{c['hours_since_job']:.0f}"))]
        html = ""
        for k, label, val in rows:
            html += (f"<div style='display:flex;justify-content:space-between;font-size:.85rem'><span>{label} "
                     f"<span class='ek-small'>({int(WEIGHTS[k] * 100)}%)</span></span><b>{val}</b></div>"
                     f"{bar(c[k], '#0B7A3E' if k != 'fairness' else '#F28C28')}<div style='height:8px'></div>")
        st.markdown(html, unsafe_allow_html=True)
        st.caption(t("why_worker_note", score=f"{c['score']:.2f}"))


# ------------------------------------------------------------------ C1 home
def home():
    me = _me()
    app_bar(t("hello", name=me["name"].split()[0]))
    st.markdown(f"<div class='ek-muted' style='margin-top:-8px;margin-bottom:10px'>📍 {esc(me['address'])}</div>",
                unsafe_allow_html=True)
    a = engine.active_for_customer(me["customer_id"])
    if a and a["status"] != "paid":
        s = t(f"st_{a['status']}")
        card(f"<b>{svc(a['service_id'])}</b> · {s}<br><span class='ek-small'>{t('booking')} #{a['booking_id']}</span>",
             "green")
        if st.button(t("track_booking"), type="primary", use_container_width=True):
            st.session_state.current_booking = a["booking_id"]
            st.switch_page(page("c_track"))

    with st.container(key="emergency"):
        if st.button("🚨  " + t("emergency_btn"), use_container_width=True):
            _start_booking(btype="emergency")
    st.caption(t("emergency_sub"))

    with st.container(border=True):
        st.markdown(f"**✨ {t('describe_title')}**")
        text = st.text_input(t("describe_label"), placeholder=t("describe_ph"), label_visibility="collapsed",
                             key="desc_text")
        c1, c2 = st.columns(2)
        with c1:
            audio = st.audio_input(t("speak"), key="voice")
        with c2:
            photo = st.file_uploader(t("add_photo"), type=["jpg", "jpeg", "png"], key="photo")
        if st.button(t("find_service"), use_container_width=True):
            txt, res = text, None
            if audio is not None and not txt:
                with st.spinner(t("listening")):
                    tr = ai_assist.transcribe(audio.getvalue())
                if tr:
                    txt = tr
                    st.session_state.heard = tr
                else:
                    st.info(t("voice_unavailable"))
            if txt:
                res = ai_assist.interpret(txt)
            if not res and photo is not None:
                with st.spinner(t("reading_photo")):
                    res = ai_assist.classify_photo(photo.getvalue(), photo.type or "image/jpeg")
                if not res:
                    st.info(t("photo_unavailable"))
            if res:
                res["text"] = txt
                st.session_state.interp = res
            elif txt:
                st.warning(t("not_understood"))
        res = st.session_state.get("interp")
        if res:
            it = pricing.issue(res["issue_id"])
            urg = res["urgency"] == "emergency"
            heard = st.session_state.get("heard")
            card((f"<div class='ek-small'>🎙 “{esc(heard)}”</div>" if heard else "")
                 + f"<div class='ek-small'>{t('we_understood')}</div>"
                 f"<b>{SERVICE_BY_ID[res['service_id']]['icon']} {svc(res['service_id'])} · {esc(issue_name(it))}</b><br>"
                 + (badge("🚨 " + t("urgent"), "red") if urg else badge(t("not_urgent"), "green"))
                 + f"<span class='ek-small'> {t('confidence')} {res['confidence'] * 100:.0f}% · "
                 f"{'AI' if res['source'] == 'ai' else t('smart_rules')}</span>", "orange")
            b1, b2 = st.columns(2)
            if b1.button(t("continue"), type="primary", use_container_width=True, key="interp_go"):
                st.session_state.pop("interp", None)
                st.session_state.pop("heard", None)
                _start_booking(res["service_id"], res["issue_id"], "emergency" if urg else "now", res.get("text", ""))
            if b2.button(t("change"), use_container_width=True, key="interp_no"):
                st.session_state.pop("interp", None)
                st.session_state.pop("heard", None)
                st.rerun()

    st.markdown(f"##### {t('all_services')}")
    with st.container(key="tiles"):
        for row in (SERVICES[:3], SERVICES[3:]):
            cols = st.columns(3)
            for col, s in zip(cols, row):
                if col.button(f"{s['icon']}\n{svc(s['service_id'])}", key=f"tile_{s['service_id']}",
                              use_container_width=True):
                    _start_booking(s["service_id"])
    card(f"🤝 <b>{t('trust_title')}</b><br><span class='ek-small'>{t('trust_sub')}</span>", "green")
    _nav()


# ------------------------------------------------------------------ C2/C3 book
def book():
    me = _me()
    b = st.session_state.get("book") or {"service_id": None, "issue_id": None, "btype": "now", "desc": ""}
    emergency = b["btype"] == "emergency"
    app_bar(t("emergency_booking") if emergency else t("book_service"))
    if emergency:
        card(f"🚨 <b>{t('emergency_booking')}</b><br><span class='ek-small'>{t('emergency_note')}</span>", "emergency")
    sids = [s["service_id"] for s in SERVICES]
    idx = sids.index(b["service_id"]) if b["service_id"] in sids else 0
    service_id = st.selectbox(t("service"), sids, index=idx,
                              format_func=lambda s: f"{SERVICE_BY_ID[s]['icon']}  {svc(s)}")
    issues = pricing.issues_for(service_id)
    ids = issues.issue_id.tolist()
    if b["issue_id"] in ids and service_id == b["service_id"]:
        default = ids.index(b["issue_id"])
    elif emergency and issues.urgent.any():
        default = ids.index(issues[issues.urgent == 1].issue_id.iloc[0])
    else:
        default = 0
    names = {r.issue_id: r for r in issues.itertuples()}
    issue_id = st.radio(t("what_problem"), ids, index=default,
                        format_func=lambda i: f"{issue_name(names[i]._asdict())} — {inr(names[i].base_price)}")
    desc = st.text_area(t("add_details"), value=b.get("desc", ""), height=68, placeholder=t("details_ph"))

    slot_date, block, btype = today().isoformat(), current_block(), b["btype"]
    if not emergency:
        when = st.segmented_control(t("when"), ["now", "scheduled"], default="now" if btype != "scheduled" else "scheduled",
                                    format_func=lambda x: t("now") if x == "now" else t("schedule"))
        btype = when or "now"
        if btype == "scheduled":
            c1, c2 = st.columns(2)
            d = c1.date_input(t("date"), value=today() + timedelta(days=1), min_value=today(),
                              max_value=today() + timedelta(days=7))
            block = c2.selectbox(t("time_slot"), [x["id"] for x in TIME_BLOCKS],
                                 format_func=lambda x: f"{block_label(x)} ({next(tb['hours'] for tb in TIME_BLOCKS if tb['id'] == x)})")
            slot_date = d.isoformat()

    st.markdown(f"**📍 {t('service_address')}**")
    st.markdown(f"<div class='ek-small' style='margin-bottom:6px'>{esc(me['address'])}</div>", unsafe_allow_html=True)
    point_map(me["lat"], me["lon"], tooltip=me["address"], height=150, key="book_map")

    it = names[issue_id]
    efee = SERVICE_BY_ID[service_id]["emergency_fee"] if emergency else 0
    rows = f"<div style='display:flex;justify-content:space-between'><span>{esc(issue_name(it._asdict()))}</span><b>{inr(it.base_price)}</b></div>"
    if efee:
        rows += f"<div style='display:flex;justify-content:space-between'><span>{t('emergency_fee')}</span><b>{inr(efee)}</b></div>"
    card(f"<div class='ek-small' style='margin-bottom:4px'>{t('price_card')}</div>{rows}"
         f"<hr style='margin:8px 0;border-color:#E3EAE4'><div style='display:flex;justify-content:space-between'>"
         f"<b>{t('estimate')}</b><b class='ek-price'>{inr(it.base_price + efee)}</b></div>"
         f"<div class='ek-small' style='margin-top:4px'>{t('price_note')}</div>", "green")
    label = t("confirm_emergency") if emergency else t("confirm_booking")
    if st.button(label, type="primary", use_container_width=True):
        zone = ZONE_BY_ID[me["zone_id"]]
        bid = engine.create_booking(me["customer_id"], service_id, issue_id, btype, slot_date, block, me["address"],
                                    me["lat"], me["lon"], me["zone_id"], zone["coop_id"], desc)
        st.session_state.current_booking = bid
        st.session_state.pop("book", None)
        st.session_state.pop("rated", None)
        st.switch_page(page("c_track"))
    if st.button(t("back"), use_container_width=True):
        st.switch_page(page("c_home"))


# ------------------------------------------------------------------ C4–C6 track
@st.fragment(run_every=2)
def _matching_panel(bid):
    b = engine.tick(bid)
    if b["status"] != "matching":
        st.rerun()
    reqs = engine.requests(bid)
    elapsed = int(engine._age(b["created_at"]))
    if b["btype"] == "emergency":
        card(f"""<div style="font-size:1.6rem">📡</div><b>{t('broadcasting')}</b><br>
             <span class='ek-small'>{t('radius_info', km=int(b['radius_km']), n=len(reqs))}</span>
             {bar((int(b['round_no']) + 1) / len(EMERGENCY_RADII), '#E0561B')}
             <div class='ek-small' style='margin-top:6px'>{t('no_surge')} · {elapsed}s</div>""", "emergency")
    else:
        pend = reqs[reqs.response == "pending"]
        who = (f"{t('offer_sent_to')} <b>{esc(pend.iloc[0]['name'])}</b> ({pend.iloc[0]['distance_km']:.1f} km)"
               if not pend.empty else "")
        card(f"""<div style="font-size:1.6rem">🔎</div><b>{t('finding_worker')}</b><br>
             <span class='ek-small'>{who}</span><div class='ek-small' style='margin-top:4px'>{t('checked_n', n=len(reqs))} · {elapsed}s</div>""",
             "green")


@st.fragment(run_every=3)
def _status_panel(bid):
    b = engine.tick(bid)
    stage = {"en_route": 1, "in_progress": 2, "completed": 3, "paid": 4, "rated": 4}.get(b["status"], 0)
    timeline([t("tl_assigned"), t("tl_on_way"), t("tl_working"), t("tl_done"), t("tl_paid")], stage)
    if b["status"] == "en_route":
        card(f"🛵 <b>{t('on_the_way')}</b><br><span class='ek-small'>{t('share_otp')}</span>"
             f"<div class='ek-big' style='letter-spacing:.3em;margin-top:4px'>{b['start_otp']}</div>", "orange")
    elif b["status"] == "in_progress":
        card(f"🛠 <b>{t('work_in_progress')}</b><br><span class='ek-small'>{t('started_at')} "
             f"{(b['started_at'] or '')[11:16]}</span>", "green")
    extras = json.loads(b["extras"] or "[]")
    for i, e in enumerate(extras):
        if not e["approved"]:
            card(f"➕ <b>{t('extra_requested')}</b><br>{esc(e['name'])} — <b>{inr(e['price'])}</b>", "orange")
            c1, c2 = st.columns(2)
            if c1.button(t("approve"), key=f"ap_{bid}_{i}", type="primary", use_container_width=True):
                engine.set_extra(bid, i, True); st.rerun(scope="fragment")
            if c2.button(t("reject"), key=f"rj_{bid}_{i}", use_container_width=True):
                engine.set_extra(bid, i, False); st.rerun(scope="fragment")
        else:
            st.markdown(f"<div class='ek-small'>✔ {esc(e['name'])} — {inr(e['price'])} ({t('approved')})</div>",
                        unsafe_allow_html=True)
    if b["status"] in ("completed", "paid", "rated"):
        card(f"✅ <b>{t('job_completed')}</b>", "green")
        if st.button(t("proceed_payment") if b["status"] == "completed" else t("view_invoice"), type="primary",
                     use_container_width=True, key="to_pay"):
            st.switch_page(page("c_pay"))


def track():
    app_bar(t("track_title"))
    bid = _current_bid()
    if not bid:
        card(t("no_active"))
        if st.button(t("book_service"), type="primary", use_container_width=True):
            st.switch_page(page("c_home"))
        _nav()
        return
    b = engine.get(bid)
    it = pricing.issue(b["issue_id"])
    st.markdown(f"**{SERVICE_BY_ID[b['service_id']]['icon']} {svc(b['service_id'])} · {esc(issue_name(it))}**  \n"
                f"<span class='ek-small'>{t('booking')} #{bid} · "
                f"{t('emergency') if b['btype'] == 'emergency' else (t('now') if b['btype'] == 'now' else block_label(b['block']) + ', ' + b['slot_date'])}</span>",
                unsafe_allow_html=True)
    if b["status"] == "matching":
        _matching_panel(bid)
        if st.button(t("cancel_booking"), use_container_width=True):
            engine.cancel(bid); st.session_state.pop("current_booking", None); st.switch_page(page("c_home"))
    elif b["status"] == "no_worker_found":
        card(f"😔 <b>{t('no_worker')}</b><br><span class='ek-small'>{t('no_worker_sub')}</span>", "orange")
        if st.button(t("schedule_earliest"), type="primary", use_container_width=True):
            st.session_state.pop("current_booking", None)
            st.session_state.book = {"service_id": b["service_id"], "issue_id": b["issue_id"], "btype": "scheduled",
                                     "desc": b["description"] or ""}
            st.switch_page(page("c_book"))
        if st.button(t("back_home"), use_container_width=True):
            st.session_state.pop("current_booking", None); st.switch_page(page("c_home"))
    elif b["status"] == "cancelled":
        card(t("cancelled"))
        st.session_state.pop("current_booking", None)
    else:
        w = engine.worker(b["worker_id"])
        worker_trust_card(w, b["service_id"])
        why_this_worker(bid, w["worker_id"])
        if b["status"] in ("en_route", "in_progress"):
            km, mins, src = route_map(w["lat"], w["lon"], b["lat"], b["lon"], w["name"], t("you"), height=210,
                                      key=f"trk_{bid}")
            st.markdown(f"<div class='ek-small'>🛣 {km:.1f} km · {t('eta')} ~{mins:.0f} {t('min')}"
                        f"{'' if src == 'road' else ' (' + t('estimated') + ')'}</div>", unsafe_allow_html=True)
        _status_panel(bid)
        if b["status"] == "en_route" and st.button(t("cancel_booking"), use_container_width=True):
            engine.cancel(bid); st.session_state.pop("current_booking", None); st.switch_page(page("c_home"))
    _nav()


# ------------------------------------------------------------------ C7–C8 pay, invoice, rating
def _upi_qr(amount, ref):
    img = qrcode.make(f"upi://pay?pa=ekkarya-demo@upi&pn=Ek%20Kaarya&am={amount:.2f}&tn=Booking%20{ref}&cu=INR",
                      box_size=6, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def pay():
    app_bar(t("payment"))
    bid = _current_bid()
    b = engine.get(bid) if bid else None
    if not b or b["status"] not in ("completed", "paid", "rated"):
        card(t("nothing_to_pay"))
        _nav()
        return
    w = engine.worker(b["worker_id"])
    me = _me()
    it = pricing.issue(b["issue_id"])
    bl = pricing.bill(b, bool(w["insured"]))
    if b["status"] == "completed":
        lines = f"<div style='display:flex;justify-content:space-between'><span>{esc(issue_name(it))}</span><b>{inr(bl['service'])}</b></div>"
        for e in bl["extras"]:
            lines += f"<div style='display:flex;justify-content:space-between'><span>{esc(e['name'])}</span><b>{inr(e['price'])}</b></div>"
        if bl["emergency_fee"]:
            lines += f"<div style='display:flex;justify-content:space-between'><span>{t('emergency_fee')}</span><b>{inr(bl['emergency_fee'])}</b></div>"
        lines += (f"<div style='display:flex;justify-content:space-between' class='ek-small'><span>{t('gst_line')}</span>"
                  f"<span>{inr(bl['gst'], 2)}</span></div>")
        card(f"<div class='ek-small'>{t('bill')}</div>{lines}<hr style='margin:8px 0;border-color:#E3EAE4'>"
             f"<div style='display:flex;justify-content:space-between'><b>{t('total')}</b>"
             f"<b class='ek-big' style='font-size:1.3rem;color:#0B7A3E'>{inr(bl['total'], 2)}</b></div>")
        card(f"<div class='ek-small'>{t('your_money')}</div>"
             f"<div style='display:flex;justify-content:space-between;font-size:.85rem'><span>👷 {t('to_worker')}</span><b>{inr(bl['worker_net'])}</b></div>"
             f"<div style='display:flex;justify-content:space-between;font-size:.85rem'><span>🏛 {t('to_coop')}</span><b>{inr(bl['coop_charge'])}</b></div>"
             f"<div style='display:flex;justify-content:space-between;font-size:.85rem'><span>🛡 {t('to_welfare')}</span><b>{inr(bl['welfare'])}</b></div>",
             "orange")
        method = st.radio(t("pay_with"), ["UPI app", "UPI QR"], horizontal=True,
                          format_func=lambda m: t("upi_app") if m == "UPI app" else t("upi_qr"))
        if method == "UPI QR":
            c1, c2, c3 = st.columns([1, 2, 1])
            c2.image(_upi_qr(bl["total"], bid), use_container_width=True)
        if st.session_state.get("pay_failed"):
            card(f"⚠️ <b>{t('pay_failed')}</b><br><span class='ek-small'>{t('pay_failed_sub')}</span>", "emergency")
        if st.button(f"{t('pay')} {inr(bl['total'], 2)}", type="primary", use_container_width=True):
            with st.spinner(t("waiting_upi")):
                time.sleep(1.6)
                p = engine.pay(bid, "UPI")
            if p is None:
                st.session_state.pay_failed = True
            else:
                st.session_state.pop("pay_failed", None)
                st.balloons()
            st.rerun()
        _nav()
        return

    p = engine.payment(bid)
    card(f"<div style='text-align:center'><div style='font-size:2.2rem'>✅</div><b>{t('pay_success')}</b><br>"
         f"<span class='ek-big' style='color:#0B7A3E'>{inr(p['total'], 2)}</span><br>"
         f"<span class='ek-small'>{p['invoice_no']} · UPI</span></div>", "green")
    pdf = invoice.build(b, p, w, me, it, bl)
    st.download_button("⬇️ " + t("download_invoice"), pdf, file_name=f"{p['invoice_no']}.pdf", mime="application/pdf",
                       use_container_width=True)
    if b["status"] == "paid" and not st.session_state.get("rated") == bid:
        with st.container(border=True):
            st.markdown(f"**{t('rate_worker', name=w['name'].split()[0])}**")
            stars = st.feedback("stars", key=f"stars_{bid}")
            tags = st.pills(t("what_went_well"), [t("tag_ontime"), t("tag_clean"), t("tag_polite"), t("tag_price"),
                                                  t("tag_explained")], selection_mode="multi", key=f"tags_{bid}")
            comment = st.text_input(t("comment"), key=f"cm_{bid}")
            if st.button(t("submit_rating"), type="primary", use_container_width=True, disabled=stars is None):
                engine.rate(bid, "customer", w["worker_id"], stars + 1, tags or [], comment)
                st.session_state.rated = bid
                st.rerun()
    else:
        card(f"🙏 <b>{t('thanks_rating')}</b>", "green")
    with st.expander("⚠️ " + t("report_problem")):
        cat = st.selectbox(t("issue_type"), ["Work quality", "Late arrival", "Price dispute", "Behaviour"],
                           format_func=lambda x: t("cat_" + x.split()[0].lower()))
        det = st.text_area(t("describe_issue"), height=70)
        if st.button(t("send_complaint"), use_container_width=True):
            engine.raise_complaint(bid, "customer", cat, det)
            st.success(t("complaint_sent", coop=COOP_BY_ID[b["coop_id"]]["name"]))
    if st.button(t("book_another"), use_container_width=True):
        st.session_state.pop("current_booking", None)
        st.switch_page(page("c_home"))
    _nav()


# ------------------------------------------------------------------ C9 bookings
def bookings():
    app_bar(t("my_bookings"))
    df = db.q("""select b.*, w.name as worker_name, p.total from bookings b
                 left join workers w on w.worker_id=b.worker_id left join payments p on p.booking_id=b.booking_id
                 where b.customer_id=? order by b.booking_id desc limit 15""", (st.session_state.user_id,))
    if df.empty:
        card(t("no_bookings"))
    kinds = {"rated": "green", "paid": "green", "cancelled": "grey", "no_worker_found": "grey"}
    for r in df.itertuples():
        it = pricing.issue(r.issue_id)
        amt = inr(r.total, 2) if r.total == r.total and r.total else inr(r.price)
        card(f"<div style='display:flex;justify-content:space-between'><b>{SERVICE_BY_ID[r.service_id]['icon']} "
             f"{svc(r.service_id)}</b>{badge(t('st_' + r.status), kinds.get(r.status, 'orange'))}</div>"
             f"<div class='ek-small'>{esc(issue_name(it))} · {r.created_at[:10]} · {esc(r.worker_name if isinstance(r.worker_name, str) else '—')}</div>"
             f"<div style='margin-top:4px'><b>{amt}</b></div>")
        if st.button(t("book_again"), key=f"again_{r.booking_id}", use_container_width=True):
            _start_booking(r.service_id, r.issue_id)
    _nav()


# ------------------------------------------------------------------ account
def account():
    me = _me()
    app_bar(t("nav_account"))
    card(f"<div class='ek-row'>{avatar(me['name'])}<div><b>{esc(me['name'])}</b><br>"
         f"<span class='ek-small'>+91 {me['phone'][:5]} {me['phone'][5:]}</span></div></div>"
         f"<div class='ek-small' style='margin-top:8px'>📍 {esc(me['address'])}</div>")
    lang_widget("acct_lang", "radio")
    card(f"📞 <b>{t('help')}</b><br><span class='ek-small'>{t('help_sub')}</span>")
    if st.button(t("logout"), use_container_width=True):
        logout(); st.rerun()
    _nav()

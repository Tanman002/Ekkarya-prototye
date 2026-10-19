"""Worker app (W1–W6): onboarding, jobs, wallet, welfare, profile."""
import json
from datetime import timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import db, engine, eshram_client, pricing
from core.config import (COLORS, COOP_BY_ID, COOPS, COOP_CHARGE_PCT, COOP_NET_MARGIN, DEMO_OFFER_TIMEOUT_S,
                         GROUP_ACCIDENT_COVER, SERVICE_BY_ID, SERVICES, SHIFT_BLOCKS, SIM_EMERG_ACCEPT_S,
                         SURPLUS_RETURN_SHARE, WELFARE_PREMIUM, ZONE_BY_ID, ZONES, now, today)
from core.i18n import LANGS, block_label, issue_name, svc, t
from core.nav import page
from core.pricing import inr
from core.ui import app_bar, avatar, badge, bottom_nav, card, esc, style_fig
from views.maps import point_map, route_map


def _me():
    return db.one("select * from workers where worker_id=?", (st.session_state.user_id,))


def _nav():
    bottom_nav([(page("w_jobs"), t("nav_jobs"), "🧰"), (page("w_wallet"), t("nav_wallet"), "💰"),
                (page("w_welfare"), t("nav_welfare"), "🛡"), (page("w_profile"), t("nav_profile"), "👤")])


def _badges(w, skills=None):
    h = badge("✔ " + t("verified"), "green") if w["kyc_status"] == "verified" else badge("⏳ " + t("under_review"), "orange")
    if w["cert_status"] == "certified":
        h += badge("🎓 " + t("certified"), "orange")
    if w["insured"]:
        h += badge("🛡 " + t("insured"), "green")
    if w["eshram_linked"]:
        h += badge("e-Shram " + t("linked"), "grey")
    return h


# ------------------------------------------------------------------ W2/W3 jobs
@st.fragment(run_every=3)
def _offers(wid):
    offers = engine.pending_offers(wid)
    if offers.empty:
        card(f"<div style='text-align:center;padding:10px 0'><div style='font-size:1.8rem'>📭</div>"
             f"<b>{t('no_requests')}</b><br><span class='ek-small'>{t('no_requests_sub')}</span></div>")
        return
    for r in offers.itertuples():
        it = pricing.issue(r.issue_id)
        em = r.btype == "emergency"
        fee = r.price + (r.emergency_fee or 0)
        age = engine._age(r.sent_at)
        left = max(0, int((SIM_EMERG_ACCEPT_S if em else DEMO_OFFER_TIMEOUT_S) - age))
        when = t("emergency") if em else (t("now") if r.btype == "now" else f"{block_label(r.block)}, {r.slot_date}")
        card(f"<div style='display:flex;justify-content:space-between'>"
             f"<b style='font-size:1.05rem'>{SERVICE_BY_ID[r.service_id]['icon']} {svc(r.service_id)}</b>"
             f"{badge('🚨 ' + t('emergency'), 'red') if em else badge(when, 'green')}</div>"
             f"<div>{esc(issue_name(it))}</div>"
             f"<div class='ek-small'>📍 {esc(ZONE_BY_ID[r.zone_id]['name'])} · {r.distance_km:.1f} km</div>"
             f"<div style='display:flex;justify-content:space-between;margin-top:6px'>"
             f"<span class='ek-big' style='font-size:1.3rem;color:#0B7A3E'>{inr(fee)}</span>"
             f"<span class='ek-small'>⏱ {left}s</span></div>", "emergency" if em else "green")
        c1, c2 = st.columns(2)
        if c1.button("✔ " + t("accept"), key=f"acc_{r.request_id}", type="primary", use_container_width=True):
            if engine.accept(r.booking_id, wid):
                st.rerun(scope="app")
            else:
                st.warning(t("already_taken"))
        if c2.button("✖ " + t("decline"), key=f"dec_{r.request_id}", use_container_width=True):
            engine.decline(r.booking_id, wid)
            st.rerun(scope="fragment")


@st.fragment(run_every=3)
def _wait_payment(bid):
    b = engine.get(bid)
    if b["status"] in ("paid", "rated"):
        st.rerun(scope="app")
    bl = pricing.bill(b, True)
    card(f"⏳ <b>{t('waiting_payment')}</b><br><span class='ek-small'>{t('customer_pays')} {inr(bl['total'], 2)}</span>",
         "orange")


def _active_job(b, w):
    bid = b["booking_id"]
    c = db.one("select * from customers where customer_id=?", (b["customer_id"],))
    it = pricing.issue(b["issue_id"])
    em = b["btype"] == "emergency"
    card(f"<div style='display:flex;justify-content:space-between'><b>{SERVICE_BY_ID[b['service_id']]['icon']} "
         f"{svc(b['service_id'])}</b>{badge('🚨 ' + t('emergency'), 'red') if em else badge(t('active_job'), 'green')}</div>"
         f"<div>{esc(issue_name(it))}</div><div class='ek-small'>👤 {esc(c['name'])} · 📍 {esc(b['address'])}</div>"
         + (f"<div class='ek-small'>📝 {esc(b['description'])}</div>" if b["description"] else ""))
    if b["status"] == "en_route":
        km, mins, _ = route_map(w["lat"], w["lon"], b["lat"], b["lon"], t("you"), c["name"], height=200,
                                key=f"wmap_{bid}")
        st.markdown(f"<div class='ek-small'>🛣 {km:.1f} km · ~{mins:.0f} {t('min')}</div>", unsafe_allow_html=True)
        otp = st.text_input(t("enter_otp"), max_chars=4, key=f"otp_{bid}", placeholder="• • • •")
        if st.button(t("start_job"), type="primary", use_container_width=True):
            if engine.start_job(bid, otp):
                st.rerun()
            else:
                st.error(t("wrong_otp"))
    elif b["status"] == "in_progress":
        card(f"🛠 <b>{t('work_in_progress')}</b> · {t('started_at')} {(b['started_at'] or '')[11:16]}", "green")
        extras = json.loads(b["extras"] or "[]")
        for e in extras:
            st.markdown(f"<div class='ek-small'>➕ {esc(e['name'])} — {inr(e['price'])} · "
                        f"{t('approved') if e['approved'] else t('awaiting_approval')}</div>", unsafe_allow_html=True)
        with st.expander("➕ " + t("add_item")):
            opts = pricing.issues_for(b["service_id"])
            opts = opts[opts.issue_id != b["issue_id"]]
            labels = {r.issue_id: f"{issue_name(r._asdict())} — {inr(r.base_price)}" for r in opts.itertuples()}
            sel = st.selectbox(t("item"), list(labels), format_func=labels.get)
            if st.button(t("send_for_approval"), use_container_width=True):
                engine.add_extra(bid, sel); st.rerun()
        if st.button("✅ " + t("mark_complete"), type="primary", use_container_width=True):
            engine.complete_job(bid); st.rerun()
    elif b["status"] == "completed":
        _wait_payment(bid)
    else:  # paid / rated
        p = engine.payment(bid)
        card(f"<div style='text-align:center'><div style='font-size:2rem'>🎉</div><b>{t('payment_received')}</b></div>"
             f"<div style='display:flex;justify-content:space-between;margin-top:8px'><span>{t('job_amount')}</span><b>{inr(p['gross'])}</b></div>"
             f"<div style='display:flex;justify-content:space-between' class='ek-small'><span>− {t('coop_charge')} ({int(COOP_CHARGE_PCT * 100)}%)</span><span>{inr(p['coop_charge'], 2)}</span></div>"
             f"<div style='display:flex;justify-content:space-between' class='ek-small'><span>− {t('welfare_premium')}</span><span>{inr(p['welfare'])}</span></div>"
             f"<hr style='margin:6px 0;border-color:#CFE7D6'><div style='display:flex;justify-content:space-between'>"
             f"<b>{t('you_earn')}</b><b class='ek-big' style='font-size:1.3rem;color:#0B7A3E'>{inr(p['worker_net'], 2)}</b></div>",
             "green")
        st.markdown(f"**{t('rate_customer')}**")
        stars = st.feedback("stars", key=f"wst_{bid}")
        if st.button(t("back_to_jobs"), type="primary", use_container_width=True):
            if stars is not None:
                engine.rate(bid, "worker", b["customer_id"], stars + 1)
            st.session_state.setdefault("worker_seen_done", set()).add(bid)
            st.rerun()


def jobs():
    w = _me()
    if not w:
        st.switch_page(page("w_onboard"))
    app_bar(t("namaste", name=w["name"].split()[0]))
    st.markdown(_badges(w), unsafe_allow_html=True)
    if w["kyc_status"] != "verified":
        card(f"⏳ <b>{t('under_review')}</b><br><span class='ek-small'>{t('under_review_sub', coop=COOP_BY_ID[w['coop_id']]['name'])}</span>",
             "orange")
        _nav()
        return
    today_net = db.one("select coalesce(sum(worker_net),0) s, count(*) n from payments where worker_id=? and paid_at>=?",
                       (w["worker_id"], today().isoformat()))
    c1, c2 = st.columns([3, 2])
    online = c1.toggle(t("online") if w["is_online"] else t("offline"), value=bool(w["is_online"]), key="online_tg")
    if online != bool(w["is_online"]):
        db.execute("update workers set is_online=? where worker_id=?", (int(online), w["worker_id"]))
        st.rerun()
    c2.markdown(f"<div style='text-align:right'><div class='ek-small'>{t('today')}</div>"
                f"<b style='color:#0B7A3E'>{inr(today_net['s'])}</b> <span class='ek-small'>· {today_net['n']} {t('jobs')}</span></div>",
                unsafe_allow_html=True)
    notes = db.q("select * from notifications where worker_id=? and is_read=0 order by notif_id desc limit 3",
                 (w["worker_id"],))
    for n in notes.itertuples():
        card(f"📣 <b>{t('coop_message')}</b><br><span class='ek-small'>{esc(n.message)}</span>", "orange")
        if st.button(t("ok_got_it"), key=f"nt_{n.notif_id}", use_container_width=True):
            db.execute("update notifications set is_read=1 where notif_id=?", (n.notif_id,)); st.rerun()

    active = engine.active_for_worker(w["worker_id"])
    seen = st.session_state.get("worker_seen_done", set())
    if active and active["status"] in ("paid", "rated"):
        done_w = db.one("select 1 from ratings where booking_id=? and from_role='worker'", (active["booking_id"],))
        if done_w or active["booking_id"] in seen or engine._age(active["accepted_at"]) > 3 * 3600:
            active = None
    if active:
        st.markdown(f"##### {t('current_job')}")
        _active_job(active, w)
    elif not online:
        card(f"😴 <b>{t('you_are_offline')}</b><br><span class='ek-small'>{t('go_online')}</span>")
    else:
        st.markdown(f"##### {t('new_requests')}")
        _offers(w["worker_id"])
    _nav()


# ------------------------------------------------------------------ W4 wallet
def wallet():
    w = _me()
    app_bar(t("nav_wallet"))
    p = db.q("select * from payments where worker_id=? order by paid_at desc", (w["worker_id"],))
    p["paid_at"] = pd.to_datetime(p.paid_at)
    t0 = pd.Timestamp(today())
    d = p[p.paid_at >= t0]
    wk = p[p.paid_at >= t0 - pd.Timedelta(days=6)]
    mo = p[p.paid_at >= t0 - pd.Timedelta(days=29)]
    c1, c2, c3 = st.columns(3)
    for col, lbl, df in ((c1, t("today"), d), (c2, t("this_week"), wk), (c3, t("last_30"), mo)):
        col.markdown(f"<div class='ek-kpi accent'><div class='l'>{lbl}</div><div class='v' style='font-size:1.1rem'>"
                     f"{inr(df.worker_net.sum())}</div><div class='s'>{len(df)} {t('jobs')}</div></div>",
                     unsafe_allow_html=True)
    st.markdown(f"##### {t('where_money_goes')} ({t('last_30')})")
    gross, cc, wel, net = mo.gross.sum(), mo.coop_charge.sum(), mo.welfare.sum(), mo.worker_net.sum()
    fig = go.Figure(go.Waterfall(
        x=[t("earned"), t("coop_charge"), t("welfare_premium"), t("you_earn")], measure=["absolute", "relative", "relative", "total"],
        y=[gross, -cc, -wel, net], text=[inr(gross), "−" + inr(cc), "−" + inr(wel), inr(net)], textposition="outside",
        increasing=dict(marker_color=COLORS["green"]), decreasing=dict(marker_color=COLORS["orange"]),
        totals=dict(marker_color=COLORS["green_dark"]), connector=dict(line=dict(color=COLORS["border"]))))
    style_fig(fig, height=270, legend=False)
    fig.update_yaxes(showticklabels=False)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    surplus = cc * COOP_NET_MARGIN * SURPLUS_RETURN_SHARE
    card(f"🏛 <b>{t('surplus_share')}</b><br><span class='ek-big' style='color:#0B7A3E'>{inr(surplus * 12)}</span>"
         f" <span class='ek-small'>/ {t('year_est')}</span><br><span class='ek-small'>{t('surplus_note')}</span>", "orange")
    agg = gross * 0.25
    card(f"📊 <b>{t('vs_aggregator')}</b><br><span class='ek-small'>{t('vs_aggregator_sub', saved=inr(agg - cc))}</span>", "green")
    st.markdown(f"##### {t('recent_jobs')}")
    rec = db.q("""select p.paid_at, b.service_id, b.issue_id, p.gross, p.worker_net from payments p
                  join bookings b on b.booking_id=p.booking_id where p.worker_id=? order by p.paid_at desc limit 8""",
               (w["worker_id"],))
    for r in rec.itertuples():
        st.markdown(f"<div style='display:flex;justify-content:space-between;font-size:.85rem;padding:4px 0;"
                    f"border-bottom:1px solid #EEF2EE'><span>{SERVICE_BY_ID[r.service_id]['icon']} "
                    f"{esc(issue_name(pricing.issue(r.issue_id)))}<br><span class='ek-small'>{r.paid_at[:16].replace('T', ' ')}</span></span>"
                    f"<b>{inr(r.worker_net)}</b></div>", unsafe_allow_html=True)
    _nav()


# ------------------------------------------------------------------ W5 welfare
def welfare():
    w = _me()
    wf = db.one("select * from welfare where worker_id=?", (w["worker_id"],))
    app_bar(t("nav_welfare"))
    if w["eshram_linked"] and w["eshram_uan"]:
        sch = eshram_client.schemes_for(w["eshram_uan"])
        card(f"<div style='display:flex;justify-content:space-between;align-items:center'><b>🇮🇳 e-Shram</b>"
             f"{badge('● ' + t('connected'), 'green')}</div>"
             f"<div class='ek-small'>UAN {eshram_client.mask_uan(w['eshram_uan'])} · {t('eshram_sub')}</div>")
        for k, label in eshram_client.SCHEMES.items():
            stt = sch.get(k, "eligible")
            st.markdown(f"<div style='display:flex;justify-content:space-between;font-size:.86rem;padding:6px 2px;"
                        f"border-bottom:1px solid #EEF2EE'><span>{label}</span>"
                        f"{badge(t('enrolled') if stt == 'enrolled' else t('eligible'), 'green' if stt == 'enrolled' else 'orange')}</div>",
                        unsafe_allow_html=True)
    else:
        card(f"🇮🇳 <b>{t('link_eshram')}</b><br><span class='ek-small'>{t('link_eshram_sub')}</span>", "orange")
        uan = st.text_input("UAN", max_chars=14)
        if st.button(t("verify_uan"), use_container_width=True):
            with st.spinner(t("connecting_eshram")):
                r = eshram_client.verify_uan(uan)
            if r["status"] == "VERIFIED":
                db.execute("update workers set eshram_uan=?, eshram_linked=1 where worker_id=?", (r["uan"], w["worker_id"]))
                st.rerun()
            else:
                st.error(t("uan_not_found"))
    st.markdown(" ")
    if wf and wf["insurance_opted"]:
        card(f"<div style='display:flex;justify-content:space-between'><b>🛡 {t('group_cover')}</b>{badge(t('active'), 'green')}</div>"
             f"<div class='ek-big' style='color:#0B7A3E'>{inr(wf['cover_amount'])}</div>"
             f"<div class='ek-small'>{t('policy')} {wf['policy_no']} · {inr(wf['premium_per_job'])} {t('per_job')}</div>"
             f"<div class='ek-small'>{t('premium_paid')}: <b>{inr(wf['total_premium_paid'])}</b></div>", "green")
        m = db.q("""select substr(paid_at,1,7) month, sum(welfare) premium from payments where worker_id=?
                    group by month order by month""", (w["worker_id"],))
        if not m.empty:
            fig = go.Figure(go.Bar(x=m.month, y=m.premium, marker_color=COLORS["green"],
                                   text=[inr(v) for v in m.premium], textposition="outside"))
            style_fig(fig, height=200, legend=False)
            fig.update_layout(title=t("contributions"))
            fig.update_yaxes(showticklabels=False)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    else:
        card(f"🛡 <b>{t('not_insured')}</b><br><span class='ek-small'>{t('not_insured_sub', p=WELFARE_PREMIUM, c=inr(GROUP_ACCIDENT_COVER))}</span>",
             "orange")
        if st.button(t("opt_in"), type="primary", use_container_width=True):
            db.execute("update welfare set insurance_opted=1, policy_no=?, cover_amount=?, premium_per_job=? where worker_id=?",
                       (f"EKGA/{w['worker_id']}/2026", GROUP_ACCIDENT_COVER, WELFARE_PREMIUM, w["worker_id"]))
            db.execute("update workers set insured=1 where worker_id=?", (w["worker_id"],))
            st.rerun()
    card(f"📞 <b>{t('claim_help')}</b><br><span class='ek-small'>{t('claim_help_sub')}</span>")
    _nav()


# ------------------------------------------------------------------ W6 profile (trust profile)
def profile():
    w = _me()
    app_bar(t("nav_profile"))
    card(f"<div class='ek-row'>{avatar(w['name'], 60)}<div><b style='font-size:1.1rem'>{esc(w['name'])}</b><br>"
         f"<span class='ek-small'>{esc(COOP_BY_ID[w['coop_id']]['name'])}</span><br>"
         f"<span class='ek-small'>{t('member_id')} {w['worker_id']} · {t('member_since')} {w['joined_on'][:7]}</span></div></div>"
         f"<div style='margin-top:8px'>{_badges(w)}</div>")
    r = db.q("select stars, tags from ratings where to_id=? and from_role='customer'", (w["worker_id"],))
    tags = pd.Series([x for s in r.tags for x in json.loads(s or "[]")]).value_counts().head(4)
    c1, c2, c3 = st.columns(3)
    c1.markdown(f"<div class='ek-kpi accent'><div class='l'>{t('rating')}</div><div class='v'>★ {w['rating_avg']:.1f}</div></div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='ek-kpi accent-o'><div class='l'>{t('jobs')}</div><div class='v'>{w['jobs_done']}</div></div>", unsafe_allow_html=True)
    c3.markdown(f"<div class='ek-kpi accent'><div class='l'>{t('experience')}</div><div class='v'>{w['years_exp']}y</div></div>", unsafe_allow_html=True)
    if len(tags):
        st.markdown(f"**{t('customers_say')}**  \n" + " ".join(badge(f"{k} · {v}", "green") for k, v in tags.items()),
                    unsafe_allow_html=True)
    st.markdown(f"**{t('skills')}**")
    sk = db.q("select * from worker_skills where worker_id=?", (w["worker_id"],))
    for s in sk.itertuples():
        st.markdown(f"<div style='display:flex;justify-content:space-between;font-size:.88rem;padding:6px 0;border-bottom:1px solid #EEF2EE'>"
                    f"<span>{SERVICE_BY_ID[s.service_id]['icon']} {svc(s.service_id)} · {s.years_exp} {t('years_exp')}</span>"
                    f"{badge(t('certified'), 'orange') if s.certified else badge(t('not_certified'), 'grey')}</div>",
                    unsafe_allow_html=True)
    st.markdown(f"**{t('verification')}**")
    items = [("🪪", t("id_check"), w["id_doc"], w["kyc_status"] == "verified"),
             ("🏛", t("coop_membership"), COOP_BY_ID[w["coop_id"]]["reg_no"], True),
             ("🇮🇳", "e-Shram", eshram_client.mask_uan(w["eshram_uan"]) if w["eshram_uan"] else "—", bool(w["eshram_linked"])),
             ("🛡", t("insured"), inr(GROUP_ACCIDENT_COVER) if w["insured"] else "—", bool(w["insured"]))]
    for ic, lb, val, ok in items:
        st.markdown(f"<div style='display:flex;justify-content:space-between;font-size:.86rem;padding:5px 0'>"
                    f"<span>{ic} {lb}<br><span class='ek-small'>{esc(val)}</span></span><span>{'✅' if ok else '⏳'}</span></div>",
                    unsafe_allow_html=True)
    st.markdown(f"<div class='ek-small'>📍 {esc(ZONE_BY_ID[w['zone_id']]['name'])} · {w['radius_km']} km · "
                f"{', '.join(block_label(b) for b in SHIFT_BLOCKS[w['shift']])}</div>", unsafe_allow_html=True)
    _nav()


# ------------------------------------------------------------------ W1 onboarding
STEPS = ["step_basic", "step_coop", "step_eshram", "step_id", "step_skills", "step_welfare"]


def onboarding():
    app_bar(t("join_title"))
    ob = st.session_state.setdefault("onboard", {"step": 0})
    step = ob["step"]
    if step >= len(STEPS):
        wid = ob.get("worker_id")
        coop = COOP_BY_ID[ob["coop_id"]]["name"]
        card(f"<div style='text-align:center'><div style='font-size:2.4rem'>🎉</div><b>{t('submitted')}</b><br>"
             f"<span class='ek-small'>{t('submitted_sub', coop=coop)}</span><br><br>"
             f"{t('member_id')}: <b>{wid}</b></div>", "green")
        if st.button(t("open_worker_app"), type="primary", use_container_width=True):
            st.session_state.role = "worker"
            st.session_state.user_id = wid
            st.session_state.pop("onboard", None)
            st.rerun()
        return
    st.progress((step + 1) / len(STEPS), text=f"{t('step')} {step + 1}/{len(STEPS)} · {t(STEPS[step])}")

    if step == 0:
        ob["name"] = st.text_input(t("full_name"), value=ob.get("name", ""))
        ob["phone"] = st.text_input(t("mobile_number"), value=ob.get("phone", "98190 22334"))
        ob["language"] = st.radio(t("language"), list(LANGS), format_func=LANGS.get, horizontal=True,
                                  index=list(LANGS).index(ob.get("language", st.session_state.get("lang", "en"))))
        ok = bool(ob["name"].strip())
    elif step == 1:
        ids = [c["coop_id"] for c in COOPS]
        ob["coop_id"] = st.radio(t("select_coop"), ids, format_func=lambda c: COOP_BY_ID[c]["name"],
                                 index=ids.index(ob.get("coop_id", "C1")))
        zs = [z["zone_id"] for z in ZONES if z["coop_id"] == ob["coop_id"]]
        ob["zone_id"] = st.selectbox(t("home_area"), zs, format_func=lambda z: ZONE_BY_ID[z]["name"],
                                     index=zs.index(ob["zone_id"]) if ob.get("zone_id") in zs else 0)
        st.text_input(t("membership_id_opt"), key="mem_id")
        ok = True
    elif step == 2:
        card(f"🇮🇳 <b>{t('eshram_title')}</b><br><span class='ek-small'>{t('eshram_why')}</span>", "green")
        uan = st.text_input(t("enter_uan"), value=ob.get("uan", ""), max_chars=14, placeholder="1002 0030 0400")
        if st.button(t("verify_uan"), type="primary", use_container_width=True):
            with st.spinner(t("connecting_eshram")):
                r = eshram_client.verify_uan(uan)
            ob["eshram"] = r
            ob["uan"] = uan
        r = ob.get("eshram")
        if r and r["status"] == "VERIFIED":
            sch = r["schemes"]
            card(f"<div style='display:flex;justify-content:space-between'><b>✅ {t('eshram_verified')}</b>{badge('e-Shram', 'green')}</div>"
                 f"<div style='font-size:.9rem;margin-top:4px'><b>{esc(r['name'])}</b> · {esc(r['occupation'])}</div>"
                 f"<div class='ek-small'>UAN {eshram_client.mask_uan(r['uan'])} · {r['district']}, {r['state']} · "
                 f"{t('registered')} {r['registered_on']}</div><div style='margin-top:4px'>"
                 + "".join(badge(f"{k.upper()}: {t('enrolled') if v == 'enrolled' else t('eligible')}",
                                 "green" if v == "enrolled" else "orange") for k, v in sch.items()) + "</div>", "green")
            if not ob.get("name"):
                ob["name"] = r["name"]
        elif r and r["status"] in ("NOT_FOUND", "INVALID"):
            st.error(t("uan_not_found"))
        if st.checkbox(t("no_uan"), value=ob.get("no_uan", False), key="no_uan_cb"):
            ob["no_uan"] = True
            card(f"ℹ️ <span class='ek-small'>{t('no_uan_help')}</span>", "orange")
        else:
            ob["no_uan"] = False
        ok = bool((r and r["status"] == "VERIFIED") or ob["no_uan"])
    elif step == 3:
        st.file_uploader(t("upload_id"), type=["jpg", "jpeg", "png", "pdf"], key="id_up")
        st.file_uploader(t("upload_photo"), type=["jpg", "jpeg", "png"], key="selfie_up")
        if st.button(t("run_ekyc"), use_container_width=True):
            with st.spinner(t("verifying")):
                import time
                time.sleep(1.2)
            ob["kyc"] = f"Aadhaar e-KYC (XXXX-XXXX-{str(abs(hash(ob.get('name', ''))))[-4:]})"
        if ob.get("kyc"):
            card(f"✅ <b>{t('ekyc_done')}</b><br><span class='ek-small'>{esc(ob['kyc'])}</span>", "green")
        ok = bool(ob.get("kyc"))
    elif step == 4:
        sids = [s["service_id"] for s in SERVICES]
        ob["skills"] = st.multiselect(t("your_skills"), sids, default=ob.get("skills", []),
                                      format_func=lambda s: f"{SERVICE_BY_ID[s]['icon']} {svc(s)}")
        ob["years"] = st.slider(t("years_experience"), 0, 30, ob.get("years", 3))
        ob["radius"] = st.select_slider(t("service_radius"), [3, 5, 6, 8, 10, 12], value=ob.get("radius", 6))
        ob["shift"] = st.radio(t("work_hours"), list(SHIFT_BLOCKS), horizontal=True, index=list(SHIFT_BLOCKS).index(ob.get("shift", "full")),
                               format_func=lambda s: t(f"shift_{s}"))
        z = ZONE_BY_ID[ob.get("zone_id", "Z01")]
        point_map(z["lat"], z["lon"], z["name"], height=150, key="ob_map")
        cert = st.file_uploader(t("upload_cert"), type=["jpg", "jpeg", "png", "pdf"], key="cert_up")
        ob["cert"] = cert is not None or ob.get("cert", False)
        ok = len(ob["skills"]) > 0
    else:
        card(f"🛡 <b>{t('group_cover')}</b> — {inr(GROUP_ACCIDENT_COVER)}<br>"
             f"<span class='ek-small'>{t('not_insured_sub', p=WELFARE_PREMIUM, c=inr(GROUP_ACCIDENT_COVER))}</span>", "green")
        ob["insured"] = st.checkbox(t("opt_in_short"), value=ob.get("insured", True))
        ob["consent"] = st.checkbox(t("consent"), value=ob.get("consent", False))
        ok = ob["consent"]

    c1, c2 = st.columns(2)
    if step > 0 and c1.button(t("back"), use_container_width=True):
        ob["step"] -= 1; st.rerun()
    last = step == len(STEPS) - 1
    if c2.button(t("submit") if last else t("next"), type="primary", use_container_width=True, disabled=not ok):
        if last:
            ob["worker_id"] = _create_worker(ob)
        ob["step"] += 1
        st.rerun()


def _create_worker(ob) -> str:
    n = db.one("select count(*) n from workers")["n"]
    wid = f"W{n + 1:04d}"
    z = ZONE_BY_ID[ob["zone_id"]]
    r = ob.get("eshram") or {}
    uan = r.get("uan") if r.get("status") == "VERIFIED" else None
    db.execute("""insert into workers(worker_id,coop_id,name,phone,language,zone_id,lat,lon,radius_km,kyc_status,cert_status,
                  id_doc,is_online,rating_avg,jobs_done,last_assigned_at,shift,eshram_uan,eshram_linked,insured,joined_on,is_demo,
                  gender,years_exp) values(?,?,?,?,?,?,?,?,?,'pending',?,?,0,0,0,null,?,?,?,?,?,0,'F',?)""",
               (wid, ob["coop_id"], ob["name"], ob["phone"].replace(" ", ""), ob["language"], ob["zone_id"], z["lat"] + 0.004,
                z["lon"] - 0.003, ob["radius"], "pending" if ob.get("cert") else "none", ob.get("kyc"), ob["shift"], uan,
                int(bool(uan)), int(ob.get("insured", False)), today().isoformat(), ob["years"]))
    db.executemany("insert into worker_skills(worker_id,service_id,years_exp,certified) values(?,?,?,0)",
                   [(wid, s, ob["years"]) for s in ob["skills"]])
    db.execute("insert into welfare(worker_id,insurance_opted,policy_no,cover_amount,premium_per_job,total_premium_paid) "
               "values(?,?,?,?,?,0)", (wid, int(ob.get("insured", False)),
                                       f"EKGA/{wid}/2026" if ob.get("insured") else None,
                                       GROUP_ACCIDENT_COVER if ob.get("insured") else 0,
                                       WELFARE_PREMIUM if ob.get("insured") else 0))
    return wid

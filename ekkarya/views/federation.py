"""Federation / Ministry dashboard (A1–A4) + AI forecast, allocation and cooperative impact."""
from datetime import timedelta

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from core import allocation, db, eshram_client
from core.config import (AGGREGATOR_COMMISSION, CHART_COLORS, COLORS, COOP_BY_ID, COOP_NET_MARGIN, COOPS,
                         DIVERGING, FEDERATION_NAME, JOBS_PER_BLOCK, SEQ_GREEN, SERVICE_NAMES_EN,
                         SURPLUS_RETURN_SHARE, TIME_BLOCKS, ZONE_BY_ID, ZONES, today)
from core.forecast import FEATURE_LABELS
from core.pricing import inr
from core.ui import app_bar, badge, card, esc, kpi_row, style_fig
from views import analytics
from views.coop import SVC_COLOR
from views.maps import markers_map

COOP_COLOR = {"C1": CHART_COLORS[0], "C2": CHART_COLORS[1], "C3": CHART_COLORS[2]}
SEQ = [[i / (len(SEQ_GREEN) - 1), c] for i, c in enumerate(SEQ_GREEN)]


def _spike_banner(spike):
    if spike:
        card("🌧️ <b>Heavy-rain alert active</b> · plumbing & electrical demand forecast raised ×1.8 for the next 3 days "
             "in Mira Road, Bhayandar, Thane West and Ghodbunder Road.", "orange")


def _coop_stats():
    t30 = (today() - timedelta(days=29)).isoformat()
    w = db.q("select coop_id, count(*) members, sum(kyc_status='verified') verified, sum(insured) insured, "
             "sum(eshram_linked) eshram, avg(rating_avg) rating, sum(is_online) online from workers group by coop_id")
    p = db.q("select coop_id, count(*) jobs, sum(gross) gross, sum(coop_charge) charge, sum(worker_net) net "
             "from payments where paid_at>=? group by coop_id", (t30,))
    c = db.q("select coop_id, sum(status='open') open_c, sum(status='escalated') esc from complaints group by coop_id")
    df = w.merge(p, on="coop_id", how="left").merge(c, on="coop_id", how="left").fillna(0)
    df["cooperative"] = df.coop_id.map(lambda x: COOP_BY_ID[x]["name"])
    return df


# ------------------------------------------------------------------ A1
def overview():
    app_bar(f"{FEDERATION_NAME} · Overview")
    _, fc, spike = analytics.get()
    _spike_banner(spike)
    df = _coop_stats()
    tot_v = df.verified.sum()
    tomorrow = (today() + timedelta(days=1)).isoformat()
    kpi_row([("Cooperatives", str(len(df)), "primary service societies"),
             ("Verified members", f"{int(tot_v)}", f"{int(df.online.sum())} online now"),
             ("Jobs (30 d)", f"{int(df.jobs.sum()):,}", inr(df.gross.sum()) + " service value"),
             ("Welfare coverage", f"{df.insured.sum() / tot_v * 100:.0f}%", "insured members"),
             ("e-Shram linked", f"{df.eshram.sum() / tot_v * 100:.0f}%", "by UAN"),
             ("Forecast tomorrow", f"{fc[fc.date == tomorrow].pred.sum():,.0f}", "bookings, all zones")])
    st.markdown(" ")
    c1, c2 = st.columns([3, 2])
    with c1:
        st.markdown("**Cooperative comparison** · last 30 days")
        show = df.assign(verified_pct=df.verified / df.members * 100, welfare_pct=df.insured / df.verified * 100,
                         eshram_pct=df.eshram / df.verified * 100)
        st.dataframe(show[["cooperative", "members", "verified_pct", "jobs", "gross", "rating", "welfare_pct",
                           "eshram_pct", "open_c", "esc"]],
                     hide_index=True, use_container_width=True,
                     column_config={"verified_pct": st.column_config.ProgressColumn("verified", format="%.0f%%", min_value=0, max_value=100),
                                    "welfare_pct": st.column_config.ProgressColumn("welfare", format="%.0f%%", min_value=0, max_value=100),
                                    "eshram_pct": st.column_config.ProgressColumn("e-Shram", format="%.0f%%", min_value=0, max_value=100),
                                    "gross": st.column_config.NumberColumn("service value ₹", format="%d"),
                                    "rating": st.column_config.NumberColumn("rating", format="★ %.2f"),
                                    "open_c": "open complaints", "esc": "escalated"})
        d = db.q("select substr(paid_at,1,10) day, coop_id, count(*) n from payments where paid_at>=? group by day, coop_id",
                 ((today() - timedelta(days=29)).isoformat(),))
        d["cooperative"] = d.coop_id.map(lambda x: COOP_BY_ID[x]["code"])
        fig = px.line(d, x="day", y="n", color="cooperative", title="Completed jobs per day",
                      color_discrete_map={COOP_BY_ID[k]["code"]: v for k, v in COOP_COLOR.items()})
        fig.update_traces(line_width=2)
        st.plotly_chart(style_fig(fig, 280), use_container_width=True)
    with c2:
        st.markdown("**Coverage map** <span class='ek-small'>· circle size = verified members, colour = cooperative</span>",
                    unsafe_allow_html=True)
        wz = db.q("select zone_id, count(*) n from workers where kyc_status='verified' group by zone_id").set_index("zone_id").n
        pts = [dict(lat=z["lat"], lon=z["lon"], color=COOP_COLOR[z["coop_id"]], radius=6 + wz.get(z["zone_id"], 0) / 2,
                    tooltip=f"{z['name']} · {COOP_BY_ID[z['coop_id']]['code']} · {wz.get(z['zone_id'], 0)} members")
               for z in ZONES]
        markers_map(pts, [19.21, 72.90], zoom=11, height=330, key="a1map")
        st.markdown(" ".join(badge(f"● {COOP_BY_ID[k]['code']} — {COOP_BY_ID[k]['name'].split(' Sahakari')[0]}", "grey")
                             for k in COOP_COLOR), unsafe_allow_html=True)
    esc_c = db.q("""select c.*, w.name worker from complaints c left join workers w on w.worker_id=c.worker_id
                    where c.status='escalated' order by c.complaint_id desc""")
    st.markdown(f"#### Escalated complaints ({len(esc_c)})")
    for r in esc_c.itertuples():
        with st.container(border=True):
            st.markdown(f"**#{r.complaint_id} · {r.category}** · {COOP_BY_ID[r.coop_id]['code']} · worker {esc(r.worker)}  \n"
                        f"{esc(r.detail)}  \n<span class='ek-small'>{esc(r.resolution or '')}</span>", unsafe_allow_html=True)
            if st.button("Mark resolved by federation", key=f"fres_{r.complaint_id}"):
                db.execute("update complaints set status='resolved', resolution='Resolved by federation ombudsman' "
                           "where complaint_id=?", (r.complaint_id,)); st.rerun()


# ------------------------------------------------------------------ A2
def forecast_page():
    app_bar("AI demand forecast · next 7 days")
    bundle, fc, spike = analytics.get()
    _spike_banner(spike)
    m = bundle["metrics"]
    kpi_row([("Model", "Gradient boosting", "Poisson loss · 11 features"),
             ("Accuracy · service/day", f"{(1 - m['mape_service_day']) * 100:.0f}%", f"MAPE {m['mape_service_day'] * 100:.1f}% on last 4 weeks"),
             ("Error · zone/service/day", f"{m['wape_zone_service_day'] * 100:.0f}%", "WAPE, finest level"),
             ("Next 7 days", f"{fc.pred.sum():,.0f}", "forecast bookings")])
    st.caption("Trained on six months of synthetic booking history with explainable seasonality (monsoon, summer AC, "
               "festival windows). Accuracy shows the pipeline works; it is not a claim about real-world demand.")
    c1, c2 = st.columns([1, 3])
    sid = c1.radio("Service", list(SERVICE_NAMES_EN), format_func=SERVICE_NAMES_EN.get)
    f = fc[fc.service_id == sid].groupby(["zone_id", "date"]).pred.sum().reset_index()
    f["zone"] = f.zone_id.map(lambda z: ZONE_BY_ID[z]["name"])
    f["day"] = pd.to_datetime(f.date).dt.strftime("%a %d")
    piv = f.pivot(index="zone", columns="day", values="pred")
    piv = piv[sorted(piv.columns, key=lambda d: f[f.day == d].date.iloc[0])]
    with c2:
        fig = go.Figure(go.Heatmap(z=piv.values, x=piv.columns, y=piv.index, colorscale=SEQ, xgap=2, ygap=2,
                                   text=np.round(piv.values).astype(int), texttemplate="%{text}",
                                   hovertemplate="%{y} · %{x}<br>%{z:.1f} bookings<extra></extra>",
                                   colorbar=dict(title="bookings", thickness=10)))
        fig.update_layout(title=f"{SERVICE_NAMES_EN[sid]} — forecast bookings by zone and day")
        st.plotly_chart(style_fig(fig, 420, legend=False), use_container_width=True)
    c1, c2 = st.columns([3, 2])
    with c1:
        h = bundle["holdout"]
        h = h[h.service_id == sid]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=h.date, y=h.bookings, name="Actual", mode="lines", line=dict(color=COLORS["green"], width=2)))
        fig.add_trace(go.Scatter(x=h.date, y=h.pred, name="Forecast", mode="lines",
                                 line=dict(color=COLORS["orange"], width=2, dash="dot")))
        fig.update_layout(title=f"Back-test · forecast vs actual, last 4 weeks · WAPE {m['per_service'][sid] * 100:.0f}%",
                          hovermode="x unified")
        st.plotly_chart(style_fig(fig, 300), use_container_width=True)
    with c2:
        imp = bundle["importance"].head(7).iloc[::-1]
        fig = go.Figure(go.Bar(x=imp.importance, y=imp.label, orientation="h", marker_color=COLORS["green"]))
        fig.update_layout(title="What drives the forecast")
        fig.update_xaxes(showticklabels=False)
        st.plotly_chart(style_fig(fig, 300, legend=False), use_container_width=True)
    tot = fc.groupby(["date", "service_id"]).pred.sum().reset_index()
    tot["service"] = tot.service_id.map(SERVICE_NAMES_EN)
    fig = px.bar(tot, x="date", y="pred", color="service", title="All services · next 7 days",
                 color_discrete_map={SERVICE_NAMES_EN[k]: v for k, v in SVC_COLOR.items()})
    fig.update_traces(marker_line_color="#FFFFFF", marker_line_width=1)
    st.plotly_chart(style_fig(fig, 300), use_container_width=True)


# ------------------------------------------------------------------ A3
def allocation_page():
    app_bar("AI workforce allocation")
    _, fc, spike = analytics.get()
    _spike_banner(spike)
    dates = sorted(fc.date.unique())
    c1, c2, c3 = st.columns(3)
    d = c1.selectbox("Day", dates, index=1 if len(dates) > 1 else 0,
                     format_func=lambda x: pd.Timestamp(x).strftime("%a %d %b"))
    blk = c2.selectbox("Time block", [b["id"] for b in TIME_BLOCKS], format_func=lambda b: b.title())
    svcs = c3.multiselect("Services", list(SERVICE_NAMES_EN), default=list(SERVICE_NAMES_EN), format_func=SERVICE_NAMES_EN.get)
    g = allocation.gaps(fc[(fc.date == d) & (fc.block == blk) & (fc.service_id.isin(svcs))])
    short = g[g.workers_needed > 0]
    kpi_row([("Forecast demand", f"{g.demand.sum():.0f}", "jobs in this block"),
             ("Capacity", f"{g.capacity.sum():.0f}", f"{JOBS_PER_BLOCK} jobs per worker per block"),
             ("Shortage slots", str(len(short)), f"{int(short.workers_needed.sum())} extra workers needed", "accent-o"),
             ("Idle capacity slots", str((g.status == 'Idle capacity').sum()), "workers who could move")])
    piv = g.pivot_table(index="zone", columns="service_id", values="gap", aggfunc="sum").rename(columns=SERVICE_NAMES_EN)
    lim = max(abs(np.nanmin(piv.values)), abs(np.nanmax(piv.values)), 1)
    fig = go.Figure(go.Heatmap(z=piv.values, x=piv.columns, y=piv.index, colorscale=DIVERGING, zmin=-lim, zmax=lim,
                               xgap=2, ygap=2, text=np.round(piv.values).astype(int), texttemplate="%{text}",
                               hovertemplate="%{y} · %{x}<br>gap %{z:.1f} jobs<extra></extra>",
                               colorbar=dict(title="gap", thickness=10)))
    fig.update_layout(title="Capacity gap (jobs) · orange = shortage, green = spare capacity")
    st.plotly_chart(style_fig(fig, 420, legend=False), use_container_width=True)

    st.markdown("#### Recommended actions")
    recs = allocation.recommendations(g, limit=10)
    if recs.empty:
        card("✅ Capacity covers forecast demand for this block.", "green")
    for i, r in enumerate(recs.itertuples()):
        zn = ZONE_BY_ID[r.zone_id]["name"]
        head = (f"**{zn} · {SERVICE_NAMES_EN[r.service_id]}** — forecast {r.demand:.0f} jobs vs capacity {r.capacity:.0f} "
                f"→ needs **{r.workers_needed}** more workers")
        with st.container(border=True):
            st.markdown(head)
            for fz, n, km in r.moves:
                c1, c2 = st.columns([4, 1])
                c1.markdown(f"↪ Move **{n}** from **{ZONE_BY_ID[fz]['name']}** ({km} km away, spare capacity)")
                if c2.button("Notify", key=f"nt_{i}_{fz}", use_container_width=True):
                    msg = (f"Extra {SERVICE_NAMES_EN[r.service_id].lower()} demand expected in {zn} on "
                           f"{pd.Timestamp(r.date).strftime('%a %d %b')} ({r.block}). Go online there to get more jobs.")
                    k = allocation.notify_workers(fz, r.service_id, n, msg)
                    st.toast(f"Notified {k} workers in {ZONE_BY_ID[fz]['name']}", icon="📣")
            if r.uncovered > 0:
                c1, c2 = st.columns([4, 1])
                c1.markdown(f"⚠️ **{r.uncovered}** still uncovered → alert off-duty members in {zn} / plan recruitment")
                if c2.button("Alert", key=f"al_{i}", use_container_width=True):
                    msg = (f"High {SERVICE_NAMES_EN[r.service_id].lower()} demand expected in {zn} on "
                           f"{pd.Timestamp(r.date).strftime('%a %d %b')} ({r.block}). Extra shifts available.")
                    k = allocation.notify_workers(r.zone_id, r.service_id, r.uncovered, msg)
                    st.toast(f"Alerted {k} members in {zn}", icon="📣")
    with st.expander("Full gap table"):
        st.dataframe(g[["zone", "service_id", "demand", "workers", "capacity", "gap", "workers_needed", "status"]]
                     .assign(service_id=lambda x: x.service_id.map(SERVICE_NAMES_EN)).sort_values("gap"),
                     hide_index=True, use_container_width=True)


# ------------------------------------------------------------------ impact (F21)
def impact():
    app_bar("Cooperative impact")
    t30 = (today() - timedelta(days=29)).isoformat()
    p = db.q("select worker_id, coop_id, gross, coop_charge, welfare, worker_net from payments where paid_at>=?", (t30,))
    gross, charge, net, wel = p.gross.sum(), p.coop_charge.sum(), p.worker_net.sum(), p.welfare.sum()
    active = p.worker_id.nunique()
    surplus = charge * COOP_NET_MARGIN
    kpi_row([("Worker share of revenue", f"{net / gross * 100:.1f}%", f"vs ~{(1 - AGGREGATOR_COMMISSION) * 100:.0f}% at a {AGGREGATOR_COMMISSION * 100:.0f}% aggregator commission"),
             ("Avg net earnings / worker", inr(net / max(active, 1)), f"last 30 days · {active} active workers"),
             ("Surplus generated", inr(surplus), f"{SURPLUS_RETURN_SHARE * 100:.0f}% returned to members"),
             ("Welfare contributions", inr(wel), "insurance pool, 30 days")])
    st.caption("Aggregator benchmark and surplus margin are assumptions set in config — verify and cite before the pitch.")
    c1, c2 = st.columns(2)
    with c1:
        base = pd.DataFrame({"model": ["Ekकार्य cooperative", "Typical aggregator"],
                             "Worker keeps": [net, gross * (1 - AGGREGATOR_COMMISSION)],
                             "Platform / coop": [charge, gross * AGGREGATOR_COMMISSION], "Welfare": [wel, 0]})
        fig = go.Figure()
        for col, color in (("Worker keeps", COLORS["green"]), ("Welfare", "#8FB339"), ("Platform / coop", COLORS["orange"])):
            fig.add_trace(go.Bar(y=base.model, x=base[col], name=col, orientation="h", marker_color=color,
                                 marker_line_color="#FFFFFF", marker_line_width=2,
                                 hovertemplate="%{y}<br>" + col + ": ₹%{x:,.0f}<extra></extra>"))
        fig.update_layout(barmode="stack", title="Where ₹ of service value goes (30 days)")
        st.plotly_chart(style_fig(fig, 300), use_container_width=True)
    with c2:
        jobs = p.groupby("worker_id").size().sort_values()
        cum = np.cumsum(jobs.values) / jobs.sum()
        x = np.arange(1, len(jobs) + 1) / len(jobs)
        gini = 1 - 2 * np.trapezoid(cum, x) if hasattr(np, "trapezoid") else 1 - 2 * np.trapz(cum, x)
        top10 = jobs.iloc[-max(1, len(jobs) // 10):].sum() / jobs.sum()
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], name="Perfect equality", mode="lines",
                                 line=dict(color="#9AA59E", dash="dot", width=1.5)))
        fig.add_trace(go.Scatter(x=np.r_[0, x], y=np.r_[0, cum], name="Ekकार्य", mode="lines",
                                 line=dict(color=COLORS["green"], width=2), fill="tonexty", fillcolor="rgba(242,140,40,.12)"))
        fig.update_layout(title=f"Work distribution · Gini {gini:.2f} · top 10% of workers do {top10 * 100:.0f}% of jobs")
        st.plotly_chart(style_fig(fig, 300), use_container_width=True)
    df = _coop_stats()
    df["welfare coverage %"] = (df.insured / df.verified * 100).round(1)
    df["net per worker (₹)"] = (df.net / df.verified).round(0)
    df["surplus (₹)"] = (df.charge * COOP_NET_MARGIN).round(0)
    st.dataframe(df[["cooperative", "verified", "jobs", "net per worker (₹)", "surplus (₹)", "welfare coverage %"]],
                 hide_index=True, use_container_width=True)


# ------------------------------------------------------------------ A4
def reports():
    app_bar("Reports")
    st.caption("CSV exports for the Ministry of Cooperation / NCCT.")
    t30 = (today() - timedelta(days=29)).isoformat()
    _, fc, _ = analytics.get()
    reps = {
        "Cooperative summary (30 days)": _coop_stats(),
        "Payments (30 days)": db.q("select * from payments where paid_at>=?", (t30,)),
        "Members": db.q("select worker_id, coop_id, name, zone_id, kyc_status, cert_status, rating_avg, jobs_done, insured, "
                        "eshram_linked from workers"),
        "Complaints": db.q("select * from complaints"),
        "7-day demand forecast": fc.assign(zone=fc.zone_id.map(lambda z: ZONE_BY_ID[z]["name"]),
                                          service=fc.service_id.map(SERVICE_NAMES_EN)),
        "e-Shram sync log": db.q("select * from eshram_sync"),
    }
    for name, df in reps.items():
        c1, c2 = st.columns([4, 1])
        c1.markdown(f"**{name}** · {len(df):,} rows")
        c2.download_button("⬇ CSV", df.to_csv(index=False).encode(), file_name=name.lower().replace(" ", "_") + ".csv",
                           mime="text/csv", key=f"dl_{name}", use_container_width=True)

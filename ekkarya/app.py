"""Ekकार्य — Cooperative Gig Services Platform (SIH 2026 · PS 26089 · Team COGNITO)

Run locally:   streamlit run app.py
Deploy:        Streamlit Community Cloud → main file app.py
"""
import streamlit as st

from core import db, nav
from core.config import APP_NAME, LOGO_SMALL
from core.ui import inject_css

st.set_page_config(page_title=f"{APP_NAME} · Cooperative services", page_icon=LOGO_SMALL, layout="wide",
                   initial_sidebar_state="collapsed")


@st.cache_resource(show_spinner="Preparing demo data…")
def _init_db(day: str):
    db.ensure_db()
    return True


from core.config import today  # noqa: E402

_init_db(today().isoformat())

from views import common, coop, customer, federation, login, worker  # noqa: E402

role = st.session_state.get("role")
MOBILE = role in (None, "customer", "worker", "worker_new")
inject_css(MOBILE)
common.sidebar()


def P(fn, title, icon, key, default=False):
    p = st.Page(fn, title=title, icon=icon, url_path=key, default=default)
    nav.PAGES[key] = p
    return p


if role is None:
    pages = [P(login.render, "Welcome", "🙏", "login", True)]
    position = "hidden"
elif role == "customer":
    pages = [P(customer.home, "Home", "🏠", "c_home", True), P(customer.book, "Book", "📝", "c_book"),
             P(customer.track, "Track", "📍", "c_track"), P(customer.pay, "Pay", "💳", "c_pay"),
             P(customer.bookings, "Bookings", "🧾", "c_bookings"), P(customer.account, "Account", "👤", "c_account")]
    position = "hidden"
elif role == "worker":
    pages = [P(worker.jobs, "Jobs", "🧰", "w_jobs", True), P(worker.wallet, "Wallet", "💰", "w_wallet"),
             P(worker.welfare, "Welfare", "🛡", "w_welfare"), P(worker.profile, "Profile", "👤", "w_profile"),
             P(worker.onboarding, "Join", "📝", "w_onboard")]
    position = "hidden"
elif role == "worker_new":
    pages = [P(worker.onboarding, "Join", "📝", "w_onboard", True)]
    position = "hidden"
elif role == "manager":
    pages = [P(coop.dashboard, "Dashboard", "📊", "m_dash", True),
             P(coop.verify, "Verification", "✅", "m_verify"),
             P(coop.members, "Members", "👥", "m_members"),
             P(coop.complaints, "Complaints", "📨", "m_complaints"),
             P(coop.rate_card, "Rate card", "🏷️", "m_rates"),
             P(coop.copilot_page, "Ops copilot", "🤝", "m_copilot"),
             P(federation.forecast_page, "Forecast", "📈", "m_forecast"),
             P(federation.allocation_page, "Allocation", "🧭", "m_alloc")]
    position = "top"
else:  # admin
    pages = [P(federation.overview, "Overview", "🇮🇳", "a_overview", True),
             P(federation.forecast_page, "Forecast", "📈", "a_forecast"),
             P(federation.allocation_page, "Allocation", "🧭", "a_alloc"),
             P(federation.impact, "Impact", "🤝", "a_impact"),
             P(coop.copilot_page, "Ops copilot", "💬", "a_copilot"),
             P(federation.reports, "Reports", "⬇️", "a_reports")]
    position = "top"

st.navigation(pages, position=position).run()

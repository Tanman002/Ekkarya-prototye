"""S0 — splash, language, role and mock OTP login."""
import streamlit as st

from core.config import APP_NAME, DEMO_PHONES
from core.i18n import LANGS, t
from core.ui import card, logo_b64
from views.common import lang_widget, login_as


def render():
    st.markdown(f"""<div style="text-align:center;margin-top:4px">
        <img src="data:image/png;base64,{logo_b64(False)}" style="height:120px"/>
        <div style="font-family:Poppins,'Noto Sans Devanagari';font-weight:700;font-size:2rem;color:#0B7A3E;margin-top:6px">{APP_NAME}</div>
        <div style="color:#5F6B63;font-size:.92rem;margin-bottom:6px">{t('tagline')}</div></div>
        <div class="ek-strip"></div>""", unsafe_allow_html=True)

    lang_widget("login_lang", "segmented", t("choose_language"))

    roles = {"customer": ("🏠", t("role_customer")), "worker": ("🧰", t("role_worker")),
             "manager": ("🏛️", t("role_manager")), "admin": ("🇮🇳", t("role_admin"))}
    role = st.radio(t("i_am"), list(roles), format_func=lambda r: f"{roles[r][0]}  {roles[r][1]}",
                    key="login_role")
    phone = st.text_input(t("mobile_number"), value=DEMO_PHONES[role], key=f"phone_{role}")
    otp = st.text_input(t("otp"), max_chars=4, placeholder="1234", key="otp")
    st.caption(t("otp_hint"))
    if st.button(t("login"), type="primary", use_container_width=True):
        if len(phone.replace(" ", "")) < 10:
            st.error(t("err_phone"))
        elif not (otp.isdigit() and len(otp) == 4):
            st.error(t("err_otp"))
        else:
            login_as(role)
            st.rerun()
    if role == "worker":
        st.markdown(" ")
        card(f"<b>{t('new_worker_q')}</b><br><span class='ek-muted'>{t('new_worker_sub')}</span>", "orange")
        if st.button(t("join_cooperative"), use_container_width=True):
            login_as("worker_new", None)
            st.rerun()

"""Design system: CSS tokens and reusable components (PRD 10.11).

Green · white · orange throughout. Pages use these helpers only — no one-off styling.
"""
import base64
import html
from functools import lru_cache

import streamlit as st

from core.config import APP_NAME, CHART_COLORS, COLORS, LOGO, LOGO_SMALL

C = COLORS


@lru_cache(maxsize=4)
def logo_b64(small: bool = True) -> str:
    with open(LOGO_SMALL if small else LOGO, "rb") as f:
        return base64.b64encode(f.read()).decode()


def esc(s) -> str:
    return html.escape(str(s if s is not None else ""))


BASE_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@500;600;700&family=Noto+Sans:wght@400;500;600;700&family=Noto+Sans+Devanagari:wght@400;500;600;700&display=swap');
html, body, .stApp, .stMarkdown, .stButton button, input, textarea, label, p, li, td, th {{
  font-family: 'Noto Sans', 'Noto Sans Devanagari', system-ui, sans-serif;
}}
h1, h2, h3, h4, .ek-title {{ font-family: 'Poppins', 'Noto Sans Devanagari', sans-serif !important; color: {C['text']}; }}
.stApp {{ background: {C['bg']}; }}
[data-testid="stAppDeployButton"], [data-testid="stMainMenu"], footer, #MainMenu {{ display: none !important; }}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stSidebar"] {{ background: #FFFFFF; border-right: 1px solid {C['border']}; }}
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {{
  border-radius: 12px; font-weight: 600; min-height: 46px; border: 1px solid {C['border']};
}}
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"], .stDownloadButton > button[kind="primary"] {{
  background: {C['green']}; border-color: {C['green']}; color: #fff;
}}
.stButton > button[kind="primary"]:hover {{ background: {C['green_dark']}; border-color: {C['green_dark']}; }}
.stButton > button[kind="secondary"]:hover {{ border-color: {C['green']}; color: {C['green']}; }}
div[data-testid="stMetric"] {{ background:#fff; border:1px solid {C['border']}; border-radius:16px; padding:12px 16px; }}
.ek-card {{ background:#fff; border-radius:16px; padding:16px 18px; border:1px solid {C['border']};
  box-shadow: 0 1px 2px rgba(16,40,24,.04); margin-bottom: 12px; }}
.ek-card.green {{ background:{C['green_light']}; border-color:#CFE7D6; }}
.ek-card.orange {{ background:{C['orange_light']}; border-color:#F7D9B8; }}
.ek-card.emergency {{ background:#FDEEE6; border-color:#F3C1A8; }}
.ek-muted {{ color:{C['muted']}; font-size: 0.86rem; }}
.ek-small {{ font-size: 0.8rem; color:{C['muted']}; }}
.ek-big {{ font-size: 1.6rem; font-weight: 700; font-family: 'Poppins', sans-serif; color:{C['text']}; }}
.ek-badge {{ display:inline-block; padding:3px 10px; border-radius:999px; font-size:0.74rem; font-weight:600;
  margin: 2px 4px 2px 0; line-height: 1.4; }}
.b-green {{ background:{C['green_light']}; color:{C['green_dark']}; border:1px solid #CFE7D6; }}
.b-orange {{ background:{C['orange_light']}; color:{C['orange_dark']}; border:1px solid #F7D9B8; }}
.b-red {{ background:#FDEEE6; color:#A63C0E; border:1px solid #F3C1A8; }}
.b-grey {{ background:#F1F3F1; color:{C['muted']}; border:1px solid {C['border']}; }}
.ek-avatar {{ width:52px; height:52px; border-radius:50%; display:flex; align-items:center; justify-content:center;
  font-weight:700; color:#fff; font-family:'Poppins',sans-serif; font-size:1.1rem; flex-shrink:0; }}
.ek-row {{ display:flex; gap:12px; align-items:center; }}
.ek-appbar {{ display:flex; align-items:center; gap:10px; margin: -4px 0 14px 0; }}
.ek-appbar img {{ height:34px; }}
.ek-appbar .name {{ font-family:'Poppins','Noto Sans Devanagari',sans-serif; font-weight:700; font-size:1.25rem; color:{C['green']}; line-height:1.1 }}
.ek-appbar .sub {{ font-size:0.8rem; color:{C['muted']}; }}
.ek-tl {{ display:flex; justify-content:space-between; margin: 6px 0 4px 0; }}
.ek-tl .step {{ flex:1; text-align:center; font-size:0.72rem; color:{C['muted']}; position:relative; }}
.ek-tl .dot {{ width:14px; height:14px; border-radius:50%; background:#DDE4DE; margin:0 auto 4px auto; }}
.ek-tl .step.done .dot {{ background:{C['green']}; }}
.ek-tl .step.now .dot {{ background:{C['orange']}; box-shadow:0 0 0 4px {C['orange_light']}; }}
.ek-tl .step.done, .ek-tl .step.now {{ color:{C['text']}; font-weight:600; }}
.ek-bar {{ height:8px; background:#EEF2EE; border-radius:99px; overflow:hidden; }}
.ek-bar > div {{ height:100%; border-radius:99px; }}
.ek-kpi {{ background:#fff; border:1px solid {C['border']}; border-radius:16px; padding:14px 16px; height:100%; }}
.ek-kpi .l {{ font-size:0.78rem; color:{C['muted']}; font-weight:600; text-transform:uppercase; letter-spacing:.03em }}
.ek-kpi .v {{ font-size:1.55rem; font-weight:700; font-family:'Poppins',sans-serif; color:{C['text']}; margin-top:2px }}
.ek-kpi .s {{ font-size:0.78rem; color:{C['muted']}; }}
.ek-kpi.accent {{ border-top: 4px solid {C['green']}; }}
.ek-kpi.accent-o {{ border-top: 4px solid {C['orange']}; }}
.ek-strip {{ background: linear-gradient(90deg, {C['orange']} 0 33%, #fff 33% 66%, {C['green']} 66% 100%);
  height: 4px; border-radius: 4px; margin: 0 0 14px 0; }}
.ek-price {{ font-weight:700; color:{C['green_dark']}; }}
.st-key-emergency button {{ background:{C['emergency']} !important; color:#fff !important; border:none !important;
  min-height:62px !important; font-size:1.05rem !important; box-shadow: 0 4px 14px rgba(224,86,27,.25); }}
.st-key-emergency button:hover {{ background:#C4470F !important; }}
.st-key-tiles button {{ min-height: 88px; background:#fff; white-space: pre-line; line-height:1.35; }}
.st-key-tiles button p {{ white-space: pre-line; }}
.st-key-tiles button:hover {{ background:{C['green_light']}; border-color:{C['green']}; color:{C['text']}; }}
.st-key-bottomnav {{ position: sticky; bottom: 0; background:#fff; border-top:1px solid {C['border']};
  padding: 4px 0 2px 0; z-index: 50; margin-top: 18px; }}
.st-key-bottomnav [data-testid="stPageLink"] a {{ justify-content:center; padding: 4px 0; }}
.st-key-bottomnav [data-testid="stPageLink"] p {{ font-size: 0.78rem; }}
.stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {{ color:{C['green']}; }}
.stTabs [data-baseweb="tab-highlight"] {{ background:{C['green']}; }}
</style>
"""

MOBILE_CSS = f"""
<style>
[data-testid="stMainBlockContainer"], .block-container {{
  max-width: 440px !important; padding: 1.3rem 1.1rem 1.2rem 1.1rem !important;
  background: #fff; border: 1px solid {C['border']}; border-radius: 28px; margin-top: 18px; margin-bottom: 24px;
  box-shadow: 0 12px 34px rgba(11,122,62,.10); min-height: 86vh;
}}
.stApp {{ background: radial-gradient(circle at 20% 0%, {C['orange_light']} 0, {C['bg']} 35%, {C['green_light']} 100%); }}
</style>
"""


def inject_css(mobile: bool):
    st.markdown(BASE_CSS, unsafe_allow_html=True)
    if mobile:
        st.markdown(MOBILE_CSS, unsafe_allow_html=True)


def app_bar(subtitle: str = "", right: str = ""):
    st.markdown(
        f"""<div class="ek-appbar"><img src="data:image/png;base64,{logo_b64()}"/>
        <div style="flex:1"><div class="name">{APP_NAME}</div><div class="sub">{esc(subtitle)}</div></div>{right}</div>
        <div class="ek-strip"></div>""", unsafe_allow_html=True)


def card(inner_html: str, kind: str = ""):
    st.markdown(f'<div class="ek-card {kind}">{inner_html}</div>', unsafe_allow_html=True)


def badge(text, kind="green") -> str:
    return f'<span class="ek-badge b-{kind}">{esc(text).replace(" ", "&nbsp;")}</span>'


AV_COLORS = [C["green"], C["orange"], "#3A6EA5", "#B5487A", "#6B4E9B", "#0B525B"]


def avatar(name: str, size: int = 52) -> str:
    initials = "".join(p[0] for p in str(name).split()[:2]).upper()
    color = AV_COLORS[sum(map(ord, str(name))) % len(AV_COLORS)]
    return (f'<div class="ek-avatar" style="background:{color};width:{size}px;height:{size}px;'
            f'font-size:{size * 0.36:.0f}px">{esc(initials)}</div>')


def kpi(label, value, sub="", accent="accent") -> str:
    return (f'<div class="ek-kpi {accent}"><div class="l">{esc(label)}</div><div class="v">{esc(value)}</div>'
            f'<div class="s">{esc(sub)}</div></div>')


def kpi_row(items):
    cols = st.columns(len(items))
    for col, it in zip(cols, items):
        col.markdown(kpi(*it), unsafe_allow_html=True)


def timeline(labels, current: int):
    parts = []
    for i, lb in enumerate(labels):
        cls = "done" if i < current else ("now" if i == current else "")
        parts.append(f'<div class="step {cls}"><div class="dot"></div>{esc(lb)}</div>')
    st.markdown(f'<div class="ek-tl">{"".join(parts)}</div>', unsafe_allow_html=True)


def bar(value: float, color=None) -> str:
    color = color or C["green"]
    return f'<div class="ek-bar"><div style="width:{max(min(value, 1), 0) * 100:.0f}%;background:{color}"></div></div>'


def bottom_nav(items):
    """items: list of (StreamlitPage, label, icon)."""
    with st.container(key="bottomnav"):
        cols = st.columns(len(items))
        for col, (page, label, icon) in zip(cols, items):
            col.page_link(page, label=label, icon=icon)


def style_fig(fig, height=320, legend=True):
    fig.update_layout(
        height=height, margin=dict(l=8, r=8, t=44, b=8), paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
        font=dict(family="Noto Sans, sans-serif", color=C["text"], size=12),
        colorway=CHART_COLORS, showlegend=legend,
        legend=dict(orientation="h", yanchor="top", y=-0.14, xanchor="left", x=0, title=None),
        hoverlabel=dict(bgcolor="#FFFFFF", font_color=C["text"], bordercolor=C["border"]),
        title_font=dict(family="Poppins, sans-serif", size=14),
    )
    fig.update_xaxes(showgrid=False, linecolor=C["border"], title=None)
    fig.update_yaxes(gridcolor="#EEF2EE", zeroline=False, title=None)
    return fig

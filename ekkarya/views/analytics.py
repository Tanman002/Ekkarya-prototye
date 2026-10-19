"""Cached model + forecast shared by cooperative and federation dashboards."""
import streamlit as st

from core import db, forecast
from core.config import today


@st.cache_resource(show_spinner="Training demand forecast model…")
def bundle(anchor: str):
    return forecast.train()


@st.cache_data(show_spinner=False, ttl=600)
def next7(anchor: str, spike: bool):
    return forecast.predict_next(bundle(anchor), 7, spike)


def get():
    a = today().isoformat()
    spike = db.get_setting("spike", "0") == "1"
    return bundle(a), next7(a, spike), spike

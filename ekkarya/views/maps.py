"""Folium map helpers (OpenStreetMap tiles, no API key)."""
import folium
import streamlit as st
from streamlit_folium import st_folium

from core.config import COLORS
from core.routing import route

TILES = "cartodbpositron"


def _pin(m, lat, lon, color, tooltip, icon):
    folium.Marker([lat, lon], tooltip=tooltip, icon=folium.Icon(color=color, icon=icon, prefix="fa")).add_to(m)


def point_map(lat, lon, tooltip="", height=180, key=None):
    m = folium.Map(location=[lat, lon], zoom_start=15, tiles=TILES, zoom_control=False)
    _pin(m, lat, lon, "green", tooltip, "home")
    st_folium(m, height=height, use_container_width=True, returned_objects=[], key=key)


def route_map(w_lat, w_lon, c_lat, c_lon, w_label="Worker", c_label="You", height=240, key=None):
    coords, km, mins, src = route(w_lat, w_lon, c_lat, c_lon)
    m = folium.Map(tiles=TILES, zoom_control=False)
    folium.PolyLine(coords, color=COLORS["green"], weight=5, opacity=0.85,
                    dash_array=None if src == "road" else "8 8").add_to(m)
    _pin(m, c_lat, c_lon, "green", c_label, "home")
    _pin(m, w_lat, w_lon, "orange", w_label, "user")
    m.fit_bounds([[min(w_lat, c_lat), min(w_lon, c_lon)], [max(w_lat, c_lat), max(w_lon, c_lon)]], padding=(30, 30))
    st_folium(m, height=height, use_container_width=True, returned_objects=[], key=key)
    return km, mins, src


def markers_map(points, center, zoom=11, height=420, key=None):
    """points: list of dict(lat, lon, color, tooltip, radius)."""
    m = folium.Map(location=center, zoom_start=zoom, tiles=TILES)
    for p in points:
        folium.CircleMarker([p["lat"], p["lon"]], radius=p.get("radius", 6), color="#FFFFFF", weight=1.5,
                            fill=True, fill_color=p["color"], fill_opacity=p.get("opacity", 0.85),
                            tooltip=p.get("tooltip")).add_to(m)
    st_folium(m, height=height, use_container_width=True, returned_objects=[], key=key)

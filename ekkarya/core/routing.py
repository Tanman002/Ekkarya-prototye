"""Road routing via the free public OSRM server, with a straight-line fallback."""
from functools import lru_cache

import requests

from core.config import AVG_SPEED_KMH
from core.matching import haversine


@lru_cache(maxsize=512)
def _route(lat1, lon1, lat2, lon2):
    try:
        r = requests.get(f"https://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}",
                         params={"overview": "full", "geometries": "geojson"}, timeout=3)
        r.raise_for_status()
        rt = r.json()["routes"][0]
        coords = tuple((c[1], c[0]) for c in rt["geometry"]["coordinates"])
        km = rt["distance"] / 1000
        return coords, km, max(km / AVG_SPEED_KMH * 60, 3), "road"
    except Exception:
        km = float(haversine(lat1, lon1, lat2, lon2)) * 1.3
        return ((lat1, lon1), (lat2, lon2)), km, max(km / AVG_SPEED_KMH * 60, 3), "estimate"


def route(lat1, lon1, lat2, lon2):
    """Returns (list of (lat, lon), km, minutes, source)."""
    c, km, mins, src = _route(round(lat1, 5), round(lon1, 5), round(lat2, 5), round(lon2, 5))
    return list(c), km, mins, src

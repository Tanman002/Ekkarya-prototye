"""AI helpers at the edges of the product (F15, F18, F19).

- interpret(text): customer's words (EN / हिंदी / मराठी / Hinglish) → service, issue, urgency
- classify_photo(bytes): photo → likely service/issue
- transcribe(bytes): voice note → text

Each uses a free-tier AI API when a key is configured in Streamlit secrets
(GEMINI_API_KEY for text & photo, GROQ_API_KEY for speech-to-text) and always falls
back to deterministic rules, so the demo never depends on an external service.
Decisions (matching, pricing) stay deterministic — AI only interprets input.
"""
import base64
import json
import os
import re

import requests

from core.config import ISSUES

URGENT_WORDS = ["urgent", "emergency", "burst", "flood", "flooding", "spark", "smoke", "shock", "fire", "asap",
                "immediately", "right now", "turant", "jaldi", "abhi", "fata", "phat", "तुरंत", "जल्दी", "अभी",
                "फट", "धुआं", "करंट", "आग", "लगेच", "ताबडतोब", "फुटला", "फुटली", "धूर", "शॉक"]

KEYWORDS = {
    "I01": ["tap", "faucet", "nal", "नल", "नळ", "tapak", "टपक", "dripping"],
    "I02": ["drain", "block", "clog", "choke", "nali", "नाली", "ड्रेन", "तुंब", "jam"],
    "I03": ["pipe", "burst", "leak", "leaking", "water everywhere", "पाइप", "पाईप", "लीक", "गळती", "paani", "पानी", "पाणी"],
    "I04": ["toilet", "flush", "commode", "टॉयलेट", "फ्लश"],
    "I05": ["switch", "socket", "plug", "स्विच", "सॉकेट", "board"],
    "I06": ["fan", "pankha", "पंखा", "ceiling fan"],
    "I07": ["short circuit", "wiring", "wire", "spark", "smoke", "shock", "current", "करंट", "वायरिंग", "शॉर्ट", "तार"],
    "I08": ["mcb", "fuse", "trip", "light gone", "no power", "power cut", "bijli", "बिजली", "लाईट", "light nahi"],
    "I09": ["ac service", "ac servicing", "ac clean", "एसी सर्विस", "ac", "एसी"],
    "I10": ["not cooling", "ac not", "ac band", "thanda nahi", "thanda", "cooling nahi", "ठंडा नहीं", "ठंडा", "थंड", "gas", "cooling"],
    "I11": ["ac install", "new ac", "install ac", "ac lagana"],
    "I12": ["bathroom", "washroom", "बाथरूम"],
    "I13": ["kitchen", "किचन", "chimney"],
    "I14": ["full home", "house clean", "deep clean", "whole house", "ghar ki safai", "घर की सफाई", "स्वच्छता", "safai", "सफाई", "diwali cleaning"],
    "I15": ["sofa", "सोफा", "couch"],
    "I16": ["door", "lock", "latch", "दरवाज", "दरवाजा", "ताला", "कुलूप", "tala"],
    "I17": ["assemble", "assembly", "furniture", "फर्नीचर", "फर्निचर", "bed"],
    "I18": ["cupboard", "drawer", "wardrobe", "almirah", "अलमारी", "कपाट", "hinge"],
    "I19": ["washing machine", "washer", "वॉशिंग"],
    "I20": ["fridge", "refrigerator", "फ्रिज"],
    "I21": ["ro", "purifier", "water filter", "प्यूरीफायर", "प्युरिफायर"],
    "I22": ["geyser", "heater", "hot water", "गीज़र", "गीझर"],
}
ISSUE_SERVICE = {i[0]: i[1] for i in ISSUES}
ISSUE_NAME = {i[0]: i[2] for i in ISSUES}


def _secret(name):
    try:
        import streamlit as st
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.environ.get(name)


def ai_available() -> dict:
    return {"text": bool(_secret("GEMINI_API_KEY")), "voice": bool(_secret("GROQ_API_KEY"))}


def _rules(text: str) -> dict | None:
    t = f" {text.lower()} "
    best, hits = None, 0
    for iid, words in KEYWORDS.items():
        h = 0
        for w in words:
            if re.search(r"[a-z]", w):
                if re.search(rf"\b{re.escape(w)}", t):
                    h += len(w.split())
            elif w in t:
                h += 1
        if h > hits:
            best, hits = iid, h
    if not best:
        return None
    urgent = any(w in t for w in URGENT_WORDS)
    return {"service_id": ISSUE_SERVICE[best], "issue_id": best, "urgency": "emergency" if urgent else "now",
            "confidence": min(0.55 + 0.15 * hits, 0.9), "source": "rules"}


def _gemini(parts) -> dict | None:
    key = _secret("GEMINI_API_KEY")
    if not key:
        return None
    model = _secret("GEMINI_MODEL") or "gemini-2.5-flash"
    catalog = "\n".join(f"{i[0]}: {i[2]} (service {i[1]})" for i in ISSUES)
    prompt = ("You route household service requests in Mumbai. Pick the single best issue id from this catalog:\n"
              f"{catalog}\nReturn only JSON: {{\"issue_id\": \"Ixx\", \"urgency\": \"emergency|now|scheduled\", "
              "\"confidence\": 0-1}. Use emergency only for safety risks or active damage (burst pipe, sparks, flooding).")
    try:
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}",
            json={"contents": [{"parts": [{"text": prompt}] + parts}],
                  "generationConfig": {"responseMimeType": "application/json", "temperature": 0}},
            timeout=12)
        r.raise_for_status()
        txt = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        d = json.loads(txt)
        iid = d.get("issue_id")
        if iid not in ISSUE_SERVICE:
            return None
        return {"service_id": ISSUE_SERVICE[iid], "issue_id": iid, "urgency": d.get("urgency", "now"),
                "confidence": float(d.get("confidence", 0.8)), "source": "ai"}
    except Exception:
        return None


def interpret(text: str) -> dict | None:
    if not text or not text.strip():
        return None
    return _gemini([{"text": f"Customer request: {text}"}]) or _rules(text)


def classify_photo(image_bytes: bytes, mime: str = "image/jpeg") -> dict | None:
    return _gemini([{"text": "Customer uploaded this photo of the problem."},
                    {"inline_data": {"mime_type": mime, "data": base64.b64encode(image_bytes).decode()}}])


def transcribe(audio_bytes: bytes) -> str | None:
    key = _secret("GROQ_API_KEY")
    if not key:
        return None
    try:
        r = requests.post("https://api.groq.com/openai/v1/audio/transcriptions",
                          headers={"Authorization": f"Bearer {key}"},
                          files={"file": ("voice.wav", audio_bytes, "audio/wav")},
                          data={"model": "whisper-large-v3"}, timeout=20)
        r.raise_for_status()
        return r.json().get("text")
    except Exception:
        return None

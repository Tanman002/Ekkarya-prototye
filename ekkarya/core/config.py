"""Central configuration for the Ekकार्य prototype.

All placeholder business values (prices, charges, premiums) live here so the team
can replace them after the rate-card research without touching any page code.
"""
import os
from datetime import date, datetime
from zoneinfo import ZoneInfo

# ---------------------------------------------------------------- paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
LANG_DIR = os.path.join(DATA_DIR, "lang")
DB_PATH = os.path.join(DATA_DIR, "ekkarya.db")
SEED_DB_PATH = os.path.join(DATA_DIR, "seed.db")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
LOGO = os.path.join(ASSETS_DIR, "logo.png")
LOGO_SMALL = os.path.join(ASSETS_DIR, "logo_small.png")

# ---------------------------------------------------------------- brand
APP_NAME = "Ekकार्य"
APP_NAME_LATIN = "Ek Kaarya"
FEDERATION_NAME = "Thane–Mumbai Suburban Service Cooperative Federation"

COLORS = {
    "green": "#0B7A3E",       # primary
    "green_dark": "#075C2E",
    "green_light": "#E8F5EC",
    "orange": "#F28C28",      # accent (logo orange)
    "orange_dark": "#B35C00",
    "orange_light": "#FFF3E6",
    "emergency": "#E0561B",   # deep saffron, emergency only
    "white": "#FFFFFF",
    "bg": "#F8FAF7",
    "text": "#1C2A22",
    "muted": "#5F6B63",
    "border": "#E3EAE4",
    "teal": "#0B525B",        # logo only
}
# Categorical chart palette (validated with the dataviz palette checker, fixed order).
CHART_COLORS = ["#0B7A3E", "#F28C28", "#3A6EA5", "#B5487A", "#8FB339", "#6B4E9B"]
SEQ_GREEN = ["#F2F8F3", "#CFE9D7", "#9ED3AF", "#5DB27E", "#228A4E", "#0B6A34"]
DIVERGING = [[0.0, "#C55A00"], [0.5, "#F1F1EE"], [1.0, "#0B7A3E"]]  # deficit orange ↔ surplus green

# ---------------------------------------------------------------- time
IST = ZoneInfo("Asia/Kolkata")


def now() -> datetime:
    """Current time in IST as a naive datetime (what the DB stores)."""
    return datetime.now(IST).replace(tzinfo=None, microsecond=0)


def today() -> date:
    return now().date()


TIME_BLOCKS = [
    {"id": "morning", "hours": "8 am – 12 pm", "start": 8, "end": 12, "share": 0.40},
    {"id": "afternoon", "hours": "12 – 5 pm", "start": 12, "end": 17, "share": 0.25},
    {"id": "evening", "hours": "5 – 9 pm", "start": 17, "end": 21, "share": 0.35},
]
SHIFT_BLOCKS = {
    "full": ["morning", "afternoon", "evening"],
    "day": ["morning", "afternoon"],
    "late": ["afternoon", "evening"],
}


def current_block() -> str:
    h = now().hour
    for b in TIME_BLOCKS:
        if b["start"] <= h < b["end"]:
            return b["id"]
    return "evening" if h >= 21 else "morning"


# Approximate festival dates used for seasonality (team to verify against the 2026 calendar).
FESTIVALS = [
    ("Gudi Padwa", date(2026, 3, 19)),
    ("Ganesh Chaturthi", date(2026, 9, 14)),
    ("Navratri", date(2026, 10, 11)),
    ("Diwali", date(2026, 11, 8)),
    ("Christmas", date(2026, 12, 25)),
]
FESTIVAL_WINDOW_DAYS = 14
MONSOON = (6, 8, 9, 30)  # 8 June – 30 September (month, day, month, day)

# ---------------------------------------------------------------- geography
ZONES = [
    {"zone_id": "Z01", "name": "Mira Road East", "lat": 19.2813, "lon": 72.8686, "weight": 1.30, "coop_id": "C1"},
    {"zone_id": "Z02", "name": "Bhayandar West", "lat": 19.3016, "lon": 72.8505, "weight": 1.05, "coop_id": "C1"},
    {"zone_id": "Z03", "name": "Dahisar", "lat": 19.2502, "lon": 72.8591, "weight": 0.90, "coop_id": "C1"},
    {"zone_id": "Z04", "name": "Borivali West", "lat": 19.2307, "lon": 72.8567, "weight": 1.20, "coop_id": "C1"},
    {"zone_id": "Z05", "name": "Kandivali West", "lat": 19.2047, "lon": 72.8376, "weight": 1.10, "coop_id": "C2"},
    {"zone_id": "Z06", "name": "Malad West", "lat": 19.1872, "lon": 72.8484, "weight": 1.15, "coop_id": "C2"},
    {"zone_id": "Z07", "name": "Thane West", "lat": 19.2000, "lon": 72.9700, "weight": 1.25, "coop_id": "C3"},
    {"zone_id": "Z08", "name": "Ghodbunder Road", "lat": 19.2580, "lon": 72.9680, "weight": 1.00, "coop_id": "C3"},
    {"zone_id": "Z09", "name": "Majiwada", "lat": 19.2240, "lon": 72.9820, "weight": 0.80, "coop_id": "C3"},
    {"zone_id": "Z10", "name": "Mulund West", "lat": 19.1726, "lon": 72.9425, "weight": 0.95, "coop_id": "C3"},
    {"zone_id": "Z11", "name": "Bhandup West", "lat": 19.1432, "lon": 72.9366, "weight": 0.75, "coop_id": "C3"},
    {"zone_id": "Z12", "name": "Powai", "lat": 19.1176, "lon": 72.9060, "weight": 0.85, "coop_id": "C2"},
]
ZONE_BY_ID = {z["zone_id"]: z for z in ZONES}

COOPS = [
    {"coop_id": "C1", "code": "MBS", "name": "Mira–Bhayandar Seva Sahakari Sanstha", "reg_no": "MH/THN/SRV/2019/0412", "lat": 19.2813, "lon": 72.8686},
    {"coop_id": "C2", "code": "MKS", "name": "Malad–Kandivali Shramik Sahakari Sanstha", "reg_no": "MH/MUM/SRV/2020/1178", "lat": 19.1960, "lon": 72.8430},
    {"coop_id": "C3", "code": "TGS", "name": "Thane Gruh Seva Sahakari Sanstha", "reg_no": "MH/THN/SRV/2018/0967", "lat": 19.2000, "lon": 72.9700},
]
COOP_BY_ID = {c["coop_id"]: c for c in COOPS}

# ---------------------------------------------------------------- services & rate card
# base_daily = expected bookings per zone per day at weight 1.0 (before seasonality)
SERVICES = [
    {"service_id": "S1", "key": "plumbing", "icon": "🔧", "emergency_fee": 150, "base_daily": 13, "occupation": "Plumber"},
    {"service_id": "S2", "key": "electrical", "icon": "⚡", "emergency_fee": 150, "base_daily": 12, "occupation": "Electrician"},
    {"service_id": "S3", "key": "ac", "icon": "❄️", "emergency_fee": 100, "base_daily": 8, "occupation": "AC Technician"},
    {"service_id": "S4", "key": "cleaning", "icon": "🧹", "emergency_fee": 100, "base_daily": 11, "occupation": "Housekeeping Worker"},
    {"service_id": "S5", "key": "carpentry", "icon": "🔨", "emergency_fee": 100, "base_daily": 5, "occupation": "Carpenter"},
    {"service_id": "S6", "key": "appliance", "icon": "🔌", "emergency_fee": 100, "base_daily": 9, "occupation": "Appliance Repair Technician"},
]
SERVICE_BY_ID = {s["service_id"]: s for s in SERVICES}
SERVICE_NAMES_EN = {
    "S1": "Plumbing", "S2": "Electrical", "S3": "AC service", "S4": "Cleaning",
    "S5": "Carpentry", "S6": "Appliance repair",
}

# Placeholder prices (₹) — replace after rate-card research (PRD 10.14).
ISSUES = [
    # id, service, en, hi, mr, price, minutes, urgent(default for emergency)
    ("I01", "S1", "Tap leak / replacement", "नल टपकना / बदलना", "नळ गळती / बदलणे", 199, 45, 0),
    ("I02", "S1", "Blocked drain", "नाली / ड्रेन जाम", "ड्रेनेज तुंबणे", 349, 60, 0),
    ("I03", "S1", "Burst or leaking pipe", "पाइप फटना / लीकेज", "पाईप फुटणे / गळती", 449, 75, 1),
    ("I04", "S1", "Toilet flush repair", "टॉयलेट फ्लश मरम्मत", "टॉयलेट फ्लश दुरुस्ती", 299, 45, 0),
    ("I05", "S2", "Switch / socket repair", "स्विच / सॉकेट मरम्मत", "स्विच / सॉकेट दुरुस्ती", 149, 30, 0),
    ("I06", "S2", "Fan installation or repair", "पंखा लगाना / मरम्मत", "पंखा बसवणे / दुरुस्ती", 249, 45, 0),
    ("I07", "S2", "Short circuit / wiring fault", "शॉर्ट सर्किट / वायरिंग खराबी", "शॉर्ट सर्किट / वायरिंग बिघाड", 399, 60, 1),
    ("I08", "S2", "MCB / fuse tripping", "MCB / फ्यूज ट्रिप", "MCB / फ्यूज ट्रिप होणे", 249, 40, 0),
    ("I09", "S3", "AC service", "AC सर्विस", "AC सर्व्हिसिंग", 549, 60, 0),
    ("I10", "S3", "AC not cooling", "AC ठंडा नहीं कर रहा", "AC थंड करत नाही", 699, 75, 1),
    ("I11", "S3", "AC installation", "AC इंस्टॉलेशन", "AC बसवणे", 1299, 120, 0),
    ("I12", "S4", "Bathroom deep clean", "बाथरूम डीप क्लीनिंग", "बाथरूम डीप क्लीनिंग", 499, 90, 0),
    ("I13", "S4", "Kitchen deep clean", "किचन डीप क्लीनिंग", "किचन डीप क्लीनिंग", 899, 150, 0),
    ("I14", "S4", "Full home cleaning (1 BHK)", "पूरे घर की सफाई (1 BHK)", "संपूर्ण घर स्वच्छता (1 BHK)", 2499, 300, 0),
    ("I15", "S4", "Sofa cleaning", "सोफा सफाई", "सोफा स्वच्छता", 599, 60, 1),
    ("I16", "S5", "Door / lock repair", "दरवाज़ा / ताला मरम्मत", "दरवाजा / कुलूप दुरुस्ती", 249, 45, 1),
    ("I17", "S5", "Furniture assembly", "फर्नीचर असेंबली", "फर्निचर जोडणी", 499, 90, 0),
    ("I18", "S5", "Cupboard / drawer repair", "अलमारी / दराज़ मरम्मत", "कपाट / ड्रॉवर दुरुस्ती", 399, 60, 0),
    ("I19", "S6", "Washing machine repair", "वॉशिंग मशीन मरम्मत", "वॉशिंग मशीन दुरुस्ती", 449, 60, 0),
    ("I20", "S6", "Refrigerator repair", "फ्रिज मरम्मत", "फ्रिज दुरुस्ती", 499, 60, 1),
    ("I21", "S6", "RO / water purifier service", "RO / वॉटर प्यूरीफायर सर्विस", "RO / वॉटर प्युरिफायर सर्व्हिसिंग", 349, 45, 0),
    ("I22", "S6", "Geyser repair", "गीज़र मरम्मत", "गीझर दुरुस्ती", 399, 45, 0),
]

# ---------------------------------------------------------------- money rules (placeholders)
COOP_CHARGE_PCT = 0.08          # cooperative service charge on gross
GST_RATE = 0.18                 # applied to the cooperative service charge only (verify with CA)
WELFARE_PREMIUM = 8             # ₹ per job to the worker's insurance pool, if opted in
GROUP_ACCIDENT_COVER = 200000   # ₹ group accident cover shown on welfare tab
SURPLUS_RETURN_SHARE = 0.5      # share of cooperative net surplus returned to members
COOP_NET_MARGIN = 0.6           # share of service charge left as surplus after costs (assumption)
AGGREGATOR_COMMISSION = 0.25    # benchmark used on impact views (verify & cite)

# ---------------------------------------------------------------- matching
W_PROXIMITY, W_RATING, W_CERT, W_FAIR = 0.40, 0.25, 0.15, 0.20
MIN_SEARCH_KM = 8
EMERGENCY_RADII = [3, 6, 10]
AVG_SPEED_KMH = 15
JOBS_PER_BLOCK = 1.5

# ---------------------------------------------------------------- demo timings (seconds)
DEMO_MODE = True
SIM_ACCEPT_S = 4            # simulated worker accepts a scheduled/now offer
DEMO_OFFER_TIMEOUT_S = 30   # live demo worker gets this long before the offer moves on
EMERG_ROUND_S = 20          # each emergency broadcast round
SIM_EMERG_ACCEPT_S = 15     # simulated workers accept emergencies after this (live worker gets a head start)
SIM_TRAVEL_S = 15           # simulated worker "travels"
SIM_WORK_S = 20             # simulated worker "works"

# ---------------------------------------------------------------- demo accounts
DEMO_CUSTOMER = "CU0001"
DEMO_WORKER = "W0001"
DEMO_MANAGER_COOP = "C1"
DEMO_NEW_UAN = "100200300400"
DEMO_PHONES = {
    "customer": "98200 11223",
    "worker": "98670 44556",
    "manager": "90040 77889",
    "admin": "91670 00123",
}

"""Rate card, payment split and invoice numbering (PRD 10.7)."""
import json

from core import db
from core.config import COOP_BY_ID, COOP_CHARGE_PCT, GST_RATE, WELFARE_PREMIUM, now


def issue(issue_id: str) -> dict:
    return db.one("select * from issues where issue_id=?", (issue_id,))


def issues_for(service_id: str):
    return db.q("select * from issues where service_id=? order by base_price", (service_id,))


def approved_extras(booking: dict) -> list:
    try:
        return [e for e in json.loads(booking.get("extras") or "[]") if e.get("approved")]
    except Exception:
        return []


def bill(booking: dict, insured: bool) -> dict:
    extras = approved_extras(booking)
    extras_total = sum(e["price"] for e in extras)
    gross = float(booking["price"]) + float(booking["emergency_fee"] or 0) + extras_total
    coop_charge = round(gross * COOP_CHARGE_PCT, 2)
    gst = round(coop_charge * GST_RATE, 2)
    welfare = WELFARE_PREMIUM if insured else 0
    return {
        "service": float(booking["price"]),
        "extras": extras,
        "extras_total": extras_total,
        "emergency_fee": float(booking["emergency_fee"] or 0),
        "gross": gross,
        "coop_charge": coop_charge,
        "gst": gst,
        "welfare": welfare,
        "worker_net": round(gross - coop_charge - welfare, 2),
        "total": round(gross + gst, 2),
    }


def invoice_no(coop_id: str, booking_id: int) -> str:
    return f"EK-{COOP_BY_ID[coop_id]['code']}-{now():%Y%m}-{int(booking_id):06d}"


def inr(x, decimals: int = 0) -> str:
    """Indian digit grouping: 123456 -> ₹1,23,456."""
    neg = x < 0
    x = abs(float(x))
    whole = int(round(x)) if decimals == 0 else int(x)
    s = str(whole)
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        s = ",".join(groups) + "," + tail
    if decimals:
        s += f"{x - whole:.{decimals}f}"[1:]
    return ("-₹" if neg else "₹") + s

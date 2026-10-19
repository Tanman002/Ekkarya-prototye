"""GST invoice PDF (fpdf2)."""
from datetime import datetime

from fpdf import FPDF

from core.config import APP_NAME_LATIN, COOP_BY_ID, COOP_CHARGE_PCT, GST_RATE, LOGO, SERVICE_NAMES_EN


class _PDF(FPDF):
    """Core fonts are Latin-1 only; map common Unicode punctuation and drop the rest."""

    def normalize_text(self, text):
        text = (str(text).replace("\u2013", "-").replace("\u2014", "-").replace("\u20b9", "Rs.")
                .replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"'))
        return super().normalize_text(text.encode("latin-1", "replace").decode("latin-1"))


def _rs(x):
    return f"Rs. {x:,.2f}"


def build(booking: dict, payment: dict, worker: dict, customer: dict, issue: dict, bill: dict) -> bytes:
    coop = COOP_BY_ID[booking["coop_id"]]
    pdf = _PDF(format="A4")
    pdf.set_auto_page_break(True, 15)
    pdf.add_page()
    try:
        pdf.image(LOGO, x=15, y=12, h=22)
    except Exception:
        pass
    pdf.set_xy(40, 13)
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(11, 122, 62)
    pdf.cell(0, 8, APP_NAME_LATIN, new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(40)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(95, 107, 99)
    pdf.cell(0, 5, "Worker-owned cooperative services platform", new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(40)
    pdf.cell(95, 5, coop["name"], new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(40)
    pdf.cell(95, 5, f"Reg. No. {coop['reg_no']}", new_x="LMARGIN", new_y="NEXT")

    pdf.set_xy(140, 13)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(28, 42, 34)
    pdf.cell(55, 7, "TAX INVOICE", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    paid = datetime.fromisoformat(payment["paid_at"])
    for line in (f"Invoice: {payment['invoice_no']}", f"Date: {paid:%d %b %Y, %I:%M %p}",
                 f"Booking: #{booking['booking_id']}"):
        pdf.set_x(140)
        pdf.cell(55, 5, line, align="R", new_x="LMARGIN", new_y="NEXT")

    pdf.set_draw_color(242, 140, 40)
    pdf.set_line_width(0.8)
    pdf.line(15, 42, 195, 42)
    pdf.set_y(47)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(90, 6, "Billed to")
    pdf.cell(90, 6, "Service provided by", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    left = [customer["name"], booking["address"], f"Phone: {customer['phone']}"]
    right = [f"{worker['name']} (Member ID {worker['worker_id']})", coop["name"],
             "ID verified | Cooperative member"]
    for a, b in zip(left, right):
        pdf.cell(90, 5, a[:55])
        pdf.cell(90, 5, b[:60], new_x="LMARGIN", new_y="NEXT")

    pdf.ln(6)
    pdf.set_fill_color(232, 245, 236)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(130, 8, "  Description", fill=True)
    pdf.cell(50, 8, "Amount  ", fill=True, align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    rows = [(f"{SERVICE_NAMES_EN[booking['service_id']]} - {issue['name_en']}", bill["service"])]
    rows += [(f"Additional item (approved): {e['name']}", e["price"]) for e in bill["extras"]]
    if bill["emergency_fee"]:
        rows.append(("Emergency visit fee (fixed, no surge)", bill["emergency_fee"]))
    rows.append((f"GST @ {int(GST_RATE * 100)}% on cooperative service charge ({_rs(bill['coop_charge'])})",
                 bill["gst"]))
    for d, amt in rows:
        pdf.cell(130, 7, "  " + d)
        pdf.cell(50, 7, _rs(amt) + "  ", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(227, 234, 228)
    pdf.set_line_width(0.3)
    pdf.line(15, pdf.get_y() + 1, 195, pdf.get_y() + 1)
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(130, 8, "  Total paid")
    pdf.set_text_color(11, 122, 62)
    pdf.cell(50, 8, _rs(bill["total"]) + "  ", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(28, 42, 34)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 6, f"  Paid via {payment['method']}  |  Status: SUCCESS", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(6)
    pdf.set_fill_color(255, 243, 230)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(0, 7, "  Where your money goes", fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    split = [("Worker earnings (paid to the worker)", bill["worker_net"]),
             (f"Cooperative service charge ({int(COOP_CHARGE_PCT * 100)}%, surplus returned to members)", bill["coop_charge"]),
             ("Worker welfare & insurance contribution", bill["welfare"]),
             ("GST to government", bill["gst"])]
    for d, amt in split:
        pdf.cell(130, 6, "  " + d)
        pdf.cell(50, 6, _rs(amt) + "  ", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(95, 107, 99)
    pdf.multi_cell(0, 4, "This is a computer-generated invoice issued by the cooperative through the Ek Kaarya platform. "
                         "For support, raise a ticket in the app. Thank you for supporting worker-owned services.")
    return bytes(pdf.output())

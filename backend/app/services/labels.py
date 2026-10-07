"""Printable labels (FR 01 spine labels). Output is PDF so any site printer can be used."""

from io import BytesIO

from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

from app.db.models import Item


def spine_label_pdf(item: Item) -> bytes:
    width, height = 1.5 * inch, 1.0 * inch
    buf = BytesIO()
    pdf = canvas.Canvas(buf, pagesize=(width, height))
    pdf.setTitle(f"Spine label {item.accession_no}")
    parts = (item.call_no or "").split()
    y = height - 0.25 * inch
    pdf.setFont("Helvetica-Bold", 11)
    for part in parts[:3]:
        pdf.drawCentredString(width / 2, y, part)
        y -= 0.2 * inch
    pdf.setFont("Helvetica", 7)
    pdf.drawCentredString(width / 2, 0.1 * inch, item.accession_no)
    pdf.showPage()
    pdf.save()
    return buf.getvalue()

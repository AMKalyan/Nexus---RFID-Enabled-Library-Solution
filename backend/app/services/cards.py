"""Patron-card personalisation (FR 04): a printable card with name, category and a Code 128 barcode."""

from io import BytesIO

from reportlab.graphics.barcode import code128
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from app.db.models import Member

CARD_SIZE = (85.6 * mm, 54 * mm)  # ID-1 card


def patron_card_pdf(member: Member, library_name: str = "Nexus Library") -> bytes:
    width, height = CARD_SIZE
    buf = BytesIO()
    pdf = canvas.Canvas(buf, pagesize=CARD_SIZE)
    pdf.setTitle(f"Library card {member.card_no}")
    pdf.setFillColorRGB(0.26, 0.22, 0.79)
    pdf.rect(0, height - 12 * mm, width, 12 * mm, fill=1, stroke=0)
    pdf.setFillColorRGB(1, 1, 1)
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(5 * mm, height - 8 * mm, library_name)
    pdf.setFillColorRGB(0, 0, 0)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(5 * mm, height - 20 * mm, member.full_name[:40])
    pdf.setFont("Helvetica", 8)
    pdf.drawString(5 * mm, height - 25 * mm, f"Category: {member.category_code}")
    barcode = code128.Code128(member.card_no, barHeight=10 * mm, barWidth=0.35 * mm)
    barcode.drawOn(pdf, 5 * mm, 8 * mm)
    pdf.drawString(5 * mm, 4 * mm, member.card_no)
    pdf.showPage()
    pdf.save()
    return buf.getvalue()

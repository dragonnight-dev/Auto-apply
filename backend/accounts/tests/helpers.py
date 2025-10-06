import io

from reportlab.pdfgen import canvas


def make_pdf(text: str = "Ann Lee\nPython developer") -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    for index, line in enumerate(text.splitlines()):
        pdf.drawString(72, 750 - index * 16, line)
    pdf.save()
    return buffer.getvalue()

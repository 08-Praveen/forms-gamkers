from datetime import datetime, timezone
from pathlib import Path
import secrets

from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas


PAGE_WIDTH = 842
PAGE_HEIGHT = 536
INK = HexColor("#173C5B")
MUTED = HexColor("#5C6E7C")
GOLD = HexColor("#B18A45")
PAPER = HexColor("#FFFEFA")
LINE = HexColor("#DCE3E8")


def render_description(description, name, college_name, certificate_number, date):
    replacements = {
        "{name}": name,
        "{college_name}": college_name,
        "{certificate_number}": certificate_number,
        "{date}": date,
    }
    for variable, value in replacements.items():
        description = description.replace(variable, value)
    return description


def generate_certificate_number(certificate_id):
    year = datetime.now(timezone.utc).year
    return f"CERT-{year}-{certificate_id:06d}"


def generate_public_token():
    return secrets.token_urlsafe(32)


def fit_font_size(text, font_name, max_size, max_width, min_size=14):
    size = max_size
    while size > min_size and stringWidth(text, font_name, size) > max_width:
        size -= 1
    return size


def wrap_text(text, font_name, font_size, max_width):
    lines = []
    for paragraph in text.splitlines() or [""]:
        current_line = ""
        for word in paragraph.split():
            if stringWidth(word, font_name, font_size) > max_width:
                if current_line:
                    lines.append(current_line)
                    current_line = ""
                chunk = ""
                for character in word:
                    if chunk and stringWidth(
                        chunk + character, font_name, font_size
                    ) > max_width:
                        lines.append(chunk)
                        chunk = character
                    else:
                        chunk += character
                current_line = chunk
                continue
            test_line = f"{current_line} {word}".strip()
            if stringWidth(test_line, font_name, font_size) <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)
    return lines


def generate_pdf(
    title,
    description,
    name,
    college_name,
    certificate_number,
    output_path,
    issue_date=None,
):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(output_path), pagesize=(PAGE_WIDTH, PAGE_HEIGHT))
    center_x = PAGE_WIDTH / 2
    content_width = PAGE_WIDTH - 210
    issue_date = issue_date or datetime.now(timezone.utc).strftime("%d %B %Y")

    pdf.setFillColor(PAPER)
    pdf.rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, fill=1, stroke=0)
    background = Path(__file__).resolve().parents[1] / "static" / "img" / "certificate-bg.png"
    pdf.drawImage(
        ImageReader(str(background)),
        0,
        0,
        width=PAGE_WIDTH,
        height=PAGE_HEIGHT,
        mask="auto",
    )

    pdf.setFillColor(INK)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawCentredString(center_x, 478, "FORMS GAMKERS")
    pdf.setStrokeColor(GOLD)
    pdf.setLineWidth(1.2)
    pdf.line(center_x - 34, 457, center_x + 34, 457)
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawCentredString(center_x, 432, "CERTIFICATE OF ACHIEVEMENT")

    title_size = fit_font_size(title, "Helvetica-Bold", 25, content_width, min_size=15)
    pdf.setFillColor(INK)
    pdf.setFont("Helvetica-Bold", title_size)
    pdf.drawCentredString(center_x, 395, title)

    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 8)
    pdf.drawCentredString(center_x, 365, "THIS CERTIFICATE IS PROUDLY PRESENTED TO")

    name_size = fit_font_size(name, "Times-Bold", 39, content_width, min_size=17)
    pdf.setFillColor(INK)
    pdf.setFont("Times-Bold", name_size)
    pdf.drawCentredString(center_x, 326, name)
    name_width = min(stringWidth(name, "Times-Bold", name_size) + 52, content_width)
    pdf.setStrokeColor(GOLD)
    pdf.setLineWidth(0.9)
    pdf.line(
        center_x - name_width / 2,
        315,
        center_x + name_width / 2,
        315,
    )

    college_size = fit_font_size(
        college_name, "Helvetica-Bold", 13, content_width, min_size=8
    )
    pdf.setFillColor(INK)
    pdf.setFont("Helvetica-Bold", college_size)
    pdf.drawCentredString(center_x, 289, college_name)

    rendered_description = render_description(
        description, name, college_name, certificate_number, issue_date
    )
    description_size = 11
    lines = wrap_text(
        rendered_description, "Helvetica", description_size, content_width
    )
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", description_size)
    description_y = 252
    for line in lines[:4]:
        pdf.drawCentredString(center_x, description_y, line)
        description_y -= 17

    pdf.setStrokeColor(LINE)
    pdf.line(100, 112, PAGE_WIDTH - 100, 112)
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica-Bold", 7)
    pdf.drawString(105, 91, "CERTIFICATE NUMBER")
    pdf.drawString(PAGE_WIDTH - 205, 91, "DATE ISSUED")
    pdf.setFillColor(INK)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(105, 73, certificate_number)
    pdf.drawString(PAGE_WIDTH - 205, 73, issue_date)
    pdf.save()

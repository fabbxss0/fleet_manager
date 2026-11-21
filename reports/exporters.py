"""Exportation d'un rapport en PDF (ReportLab) et en Excel (OpenPyXL)."""
from decimal import Decimal
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from core.models import AppSettings

NAVY = "#0B1F3A"
BLUE = "#2563EB"
LIGHT = "#F1F5F9"


def format_cell(value, money=False):
    """Mise en forme d'une valeur pour le PDF / l'aperçu (séparateur des milliers)."""
    if isinstance(value, (int, Decimal, float)) and not isinstance(value, bool):
        text = f"{int(value):,}".replace(",", " ")
        return f"{text} FCFA" if money else text
    return "" if value is None else str(value)


def _period_text(report):
    if report["date_from"] or report["date_to"]:
        start = report["date_from"].strftime("%d/%m/%Y") if report["date_from"] else "…"
        end = report["date_to"].strftime("%d/%m/%Y") if report["date_to"] else "…"
        return f"Période : du {start} au {end}"
    return "Période : toutes les données"


# --------------------------------------------------------------------------- PDF
def export_pdf(report):
    buffer = BytesIO()
    page_size = landscape(A4)
    org = AppSettings.load().organization_name
    doc = SimpleDocTemplate(buffer, pagesize=page_size, leftMargin=1.5 * cm, rightMargin=1.5 * cm,
                            topMargin=2.6 * cm, bottomMargin=1.6 * cm, title=report["title"], author="FLEET MANAGER")
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("t", parent=styles["Title"], textColor=colors.HexColor(NAVY), fontSize=18, spaceAfter=4)
    meta_style = ParagraphStyle("m", parent=styles["Normal"], textColor=colors.HexColor("#475569"), fontSize=9)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], textColor=colors.HexColor(NAVY), fontSize=12, spaceBefore=12)
    cell = ParagraphStyle("c", parent=styles["Normal"], fontSize=8, leading=10)
    cell_right = ParagraphStyle("cr", parent=cell, alignment=TA_RIGHT)
    head = ParagraphStyle("h", parent=cell, textColor=colors.white, fontName="Helvetica-Bold")

    story = [
        Paragraph(report["title"], title_style),
        Paragraph(f"{_period_text(report)} — Généré le {report['generated_at']:%d/%m/%Y à %H:%M}", meta_style),
        Spacer(1, 6),
    ]
    width = page_size[0] - doc.leftMargin - doc.rightMargin
    for section in report["sections"]:
        story.append(Paragraph(section.title, h2))
        if not section.rows:
            story.append(Paragraph("Aucune donnée pour cette section.", meta_style))
            continue
        right = set(section.money_columns) | set(section.number_columns)
        data = [[Paragraph(c, head) for c in section.columns]]
        body = section.rows + ([section.total] if section.total else [])
        for row in body:
            data.append([
                Paragraph(format_cell(v, i in section.money_columns), cell_right if i in right else cell)
                for i, v in enumerate(row)
            ])
        table = Table(data, colWidths=[width / len(section.columns)] * len(section.columns), repeatRows=1)
        style = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(NAVY)),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor(LIGHT)]),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]
        if section.total:
            style += [("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#DBEAFE")),
                      ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold")]
        table.setStyle(TableStyle(style))
        story.append(table)

    def decorate(canvas, document):
        canvas.saveState()
        w, h = page_size
        canvas.setFillColor(colors.HexColor(NAVY))
        canvas.rect(0, h - 1.6 * cm, w, 1.6 * cm, fill=1, stroke=0)
        canvas.setFillColor(colors.HexColor(BLUE))
        canvas.rect(0, h - 1.75 * cm, w, 0.15 * cm, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 14)
        canvas.drawString(1.5 * cm, h - 1.0 * cm, "FLEET MANAGER")
        canvas.setFont("Helvetica", 9)
        canvas.drawRightString(w - 1.5 * cm, h - 1.0 * cm, org)
        canvas.setFillColor(colors.HexColor("#64748B"))
        canvas.setFont("Helvetica", 8)
        canvas.drawString(1.5 * cm, 0.8 * cm, f"Document généré le {report['generated_at']:%d/%m/%Y à %H:%M}")
        canvas.drawRightString(w - 1.5 * cm, 0.8 * cm, f"Page {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
    return buffer.getvalue()


# ------------------------------------------------------------------------- Excel
def export_excel(report):
    workbook = Workbook()
    workbook.remove(workbook.active)
    thin = Side(style="thin", color="CBD5E1")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    header_fill = PatternFill("solid", fgColor=NAVY[1:])
    total_fill = PatternFill("solid", fgColor="DBEAFE")
    used_names = set()

    for section in report["sections"]:
        name = section.title[:28].replace("/", "-")
        while name in used_names:
            name = name[:26] + str(len(used_names))
        used_names.add(name)
        sheet = workbook.create_sheet(title=name)
        last_col = get_column_letter(max(len(section.columns), 1))
        sheet.merge_cells(f"A1:{last_col}1")
        sheet["A1"] = f"FLEET MANAGER — {report['title']}"
        sheet["A1"].font = Font(size=14, bold=True, color=NAVY[1:])
        sheet.merge_cells(f"A2:{last_col}2")
        sheet["A2"] = f"{section.title} | {_period_text(report)} | Généré le {report['generated_at']:%d/%m/%Y %H:%M}"
        sheet["A2"].font = Font(italic=True, color="64748B")

        header_row = 4
        for col, title in enumerate(section.columns, start=1):
            c = sheet.cell(row=header_row, column=col, value=title)
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = header_fill
            c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            c.border = border
        rows = section.rows + ([section.total] if section.total else [])
        for r_index, row in enumerate(rows, start=header_row + 1):
            is_total = section.total is not None and r_index == header_row + len(rows)
            for c_index, value in enumerate(row):
                if isinstance(value, Decimal):
                    value = int(value)
                c = sheet.cell(row=r_index, column=c_index + 1, value=value)
                c.border = border
                if c_index in section.money_columns:
                    c.number_format = '#,##0" FCFA"'
                elif c_index in section.number_columns and isinstance(value, (int, float)):
                    c.number_format = "#,##0"
                if is_total:
                    c.font = Font(bold=True)
                    c.fill = total_fill
        for col in range(1, len(section.columns) + 1):
            letter = get_column_letter(col)
            longest = max([len(str(sheet.cell(row=r, column=col).value or "")) for r in range(header_row, header_row + len(rows) + 1)] + [10])
            sheet.column_dimensions[letter].width = min(longest + 4, 45)
        sheet.freeze_panes = sheet.cell(row=header_row + 1, column=1)
        if not rows:
            sheet.cell(row=header_row + 1, column=1, value="Aucune donnée.")

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()

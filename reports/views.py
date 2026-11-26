from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.utils import timezone

from core.filters import parse_date
from core.permissions import staff_required

from .exporters import export_excel, export_pdf, format_cell
from .services import REPORTS, build_report


@staff_required
def report_index(request):
    reports = [{"key": k, "title": t, "description": desc, "icon": icon, "has_period": p}
               for k, (t, desc, icon, _f, p) in REPORTS.items()]
    return render(request, "reports/report_index.html", {"page_title": "Rapports", "reports": reports})


@staff_required
def report_view(request, key):
    """Aperçu HTML d'un rapport ; ?format=pdf ou ?format=xlsx pour l'export."""
    if key not in REPORTS:
        raise Http404("Rapport inconnu")
    date_from, date_to = parse_date(request.GET.get("du")), parse_date(request.GET.get("au"))
    if date_from and date_to and date_from > date_to:
        messages.error(request, "La date de début doit précéder la date de fin. Le filtre a été ignoré.")
        date_from = date_to = None
    report = build_report(key, date_from, date_to)
    export = request.GET.get("format")
    stamp = timezone.localtime().strftime("%Y%m%d_%H%M")
    if export == "pdf":
        response = HttpResponse(export_pdf(report), content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="rapport_{key}_{stamp}.pdf"'
        return response
    if export == "xlsx":
        response = HttpResponse(
            export_excel(report), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = f'attachment; filename="rapport_{key}_{stamp}.xlsx"'
        return response

    # Mise en forme des cellules pour l'aperçu HTML
    for section in report["sections"]:
        right = set(section.money_columns) | set(section.number_columns)
        section.display_rows = [
            [(format_cell(v, i in section.money_columns), i in right) for i, v in enumerate(row)] for row in section.rows
        ]
        section.display_total = [
            (format_cell(v, i in section.money_columns), i in right) for i, v in enumerate(section.total)
        ] if section.total else None
    return render(request, "reports/report_detail.html", {
        "page_title": report["title"], "report": report, "query": request.GET.urlencode(),
        "du": request.GET.get("du", ""), "au": request.GET.get("au", ""),
    })

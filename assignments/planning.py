"""
Planning mensuel du parc : une ligne par véhicule, une colonne par jour.

Chaque affectation ou entretien devient un « segment » (colonne de début,
nombre de jours), affiché sous forme de barre avec une grille CSS.
"""
import calendar
from datetime import date, timedelta

from django.db.models import Q
from django.utils import timezone

from maintenance.models import Maintenance
from vehicles.models import Vehicle

from .models import Assignment

MONTHS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre",
             "octobre", "novembre", "décembre"]
DAYS_FR = ["L", "M", "M", "J", "V", "S", "D"]


def parse_month(value):
    """« 2026-11 » -> date(2026, 11, 1) ; mois courant si la valeur est absente ou invalide."""
    try:
        year, month = (int(x) for x in value.split("-"))
        return date(year, month, 1)
    except (AttributeError, ValueError):
        return timezone.localdate().replace(day=1)


def _segment(start, end, first, last, **data):
    """Découpe la période [start, end] sur le mois affiché ; None si elle est hors du mois."""
    start, end = max(start, first), min(end, last)
    if end < start:
        return None
    return {"col": start.day + 1, "span": (end - start).days + 1, **data}  # +1 : la colonne 1 = véhicule


def build_planning(month_start, category=""):
    today = timezone.localdate()
    days_in_month = calendar.monthrange(month_start.year, month_start.month)[1]
    first, last = month_start, month_start.replace(day=days_in_month)
    vehicles = Vehicle.objects.exclude(status=Vehicle.Status.OUT_OF_SERVICE)
    if category:
        vehicles = vehicles.filter(category=category)

    rows = {v.pk: {"vehicle": v, "segments": []} for v in vehicles}
    assignments = (Assignment.objects.exclude(status=Assignment.Status.CANCELLED)
                   .filter(vehicle__in=rows.keys(), start_date__lte=last)
                   .filter(Q(actual_return_date__gte=first) | Q(actual_return_date__isnull=True))
                   .select_related("driver"))
    for a in assignments:
        if a.actual_return_date:
            end = a.actual_return_date
        else:  # en cours : jusqu'au retour prévu, ou jusqu'à aujourd'hui en cas de retard
            end = max(a.expected_end_date, today)
        seg = _segment(a.start_date, end, first, last, kind="overdue" if a.is_overdue else "assignment",
                       label=a.driver.full_name, url=a.get_absolute_url(),
                       title=f"{a.driver.full_name} — {a.purpose} ({a.start_date:%d/%m} → {end:%d/%m})")
        if seg:
            rows[a.vehicle_id]["segments"].append(seg)

    maintenances = (Maintenance.objects.filter(vehicle__in=rows.keys())
                    .exclude(status=Maintenance.Status.CANCELLED).filter(date__lte=last))
    for m in maintenances:
        end = today if m.status == Maintenance.Status.IN_PROGRESS else m.date
        if end < first:
            continue
        seg = _segment(m.date, end, first, last, kind="planned" if m.status == Maintenance.Status.PLANNED else "maintenance",
                       label=m.get_intervention_type_display(), url=m.get_absolute_url(),
                       title=f"{m.get_intervention_type_display()} — {m.provider} ({m.get_status_display()})")
        if seg:
            rows[m.vehicle_id]["segments"].append(seg)

    days = []
    for d in range(1, days_in_month + 1):
        current = month_start.replace(day=d)
        days.append({"day": d, "weekday": DAYS_FR[current.weekday()], "weekend": current.weekday() >= 5,
                     "today": current == today, "col": d + 1})
    prev_month = (first - timedelta(days=1)).replace(day=1)
    next_month = last + timedelta(days=1)
    busy = sum(1 for r in rows.values() if r["segments"])
    return {
        "rows": list(rows.values()), "days": days, "days_in_month": days_in_month,
        "title": f"{MONTHS_FR[month_start.month - 1].capitalize()} {month_start.year}",
        "prev": prev_month.strftime("%Y-%m"), "next": next_month.strftime("%Y-%m"),
        "current": today.strftime("%Y-%m"), "busy_count": busy,
    }

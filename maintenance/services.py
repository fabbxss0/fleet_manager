"""Logique métier des entretiens : statut du véhicule, échéances, dépenses."""
from datetime import timedelta

from django.db import transaction
from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from core.models import AppSettings
from vehicles.models import Vehicle

from .models import Maintenance


@transaction.atomic
def save_maintenance(maintenance):
    """
    Enregistre un entretien puis synchronise le véhicule :
    - un entretien « En cours » place le véhicule « En entretien » ;
    - le kilométrage du véhicule est mis à jour si l'intervention l'indique plus élevé ;
    - à la fin de l'entretien, le véhicule retrouve son statut normal.
    """
    maintenance.full_clean()
    maintenance.save()
    vehicle = Vehicle.objects.select_for_update().get(pk=maintenance.vehicle_id)
    if maintenance.mileage > vehicle.mileage and maintenance.status in (
        Maintenance.Status.IN_PROGRESS, Maintenance.Status.DONE,
    ):
        vehicle.mileage = maintenance.mileage
        vehicle.save(update_fields=["mileage", "updated_at"])
    if maintenance.status == Maintenance.Status.IN_PROGRESS and vehicle.status in (
        Vehicle.Status.AVAILABLE, Vehicle.Status.ASSIGNED,
    ):
        vehicle.status = Vehicle.Status.MAINTENANCE
        vehicle.save(update_fields=["status", "updated_at"])
    else:
        vehicle.refresh_status()
    return maintenance


def get_due_schedules():
    """
    Retourne la liste des échéances d'entretien périodique.

    Pour chaque couple (véhicule, type d'intervention), on retient le dernier
    entretien terminé possédant une date et/ou un kilométrage de prochain entretien.
    Chaque élément est un dict : maintenance, vehicle, state ('overdue' / 'soon'),
    days_left, km_left.
    """
    settings_ = AppSettings.load()
    today = timezone.localdate()
    latest = {}
    queryset = (
        Maintenance.objects.filter(status=Maintenance.Status.DONE)
        .exclude(next_date__isnull=True, next_mileage__isnull=True)
        .exclude(vehicle__status=Vehicle.Status.OUT_OF_SERVICE)
        .select_related("vehicle")
        .order_by("date", "id")
    )
    for maintenance in queryset:
        latest[(maintenance.vehicle_id, maintenance.intervention_type)] = maintenance

    # Un entretien planifié/en cours plus récent du même type couvre déjà l'échéance
    planned = set(
        Maintenance.objects.filter(status__in=[Maintenance.Status.PLANNED, Maintenance.Status.IN_PROGRESS])
        .values_list("vehicle_id", "intervention_type")
    )

    schedules = []
    for key, maintenance in latest.items():
        if key in planned:
            continue
        vehicle = maintenance.vehicle
        days_left = (maintenance.next_date - today).days if maintenance.next_date else None
        km_left = maintenance.next_mileage - vehicle.mileage if maintenance.next_mileage else None
        is_tc = maintenance.intervention_type == Maintenance.InterventionType.TECHNICAL_CONTROL
        day_threshold = settings_.technical_control_days if is_tc else settings_.maintenance_days_threshold

        if (days_left is not None and days_left < 0) or (km_left is not None and km_left < 0):
            state = "overdue"
        elif (days_left is not None and days_left <= day_threshold) or (
            km_left is not None and km_left <= settings_.maintenance_km_threshold
        ):
            state = "soon"
        else:
            continue
        schedules.append({
            "maintenance": maintenance, "vehicle": vehicle, "state": state,
            "days_left": days_left, "km_left": km_left, "is_technical_control": is_tc,
        })
    schedules.sort(key=lambda s: (s["state"] != "overdue", s["days_left"] if s["days_left"] is not None else 9999))
    return schedules


def total_cost(queryset=None):
    queryset = Maintenance.objects.all() if queryset is None else queryset
    return queryset.exclude(status=Maintenance.Status.CANCELLED).aggregate(total=Sum("cost"))["total"] or 0


def cost_by_vehicle(queryset=None):
    """Coût total des entretiens par véhicule, du plus coûteux au moins coûteux."""
    queryset = Maintenance.objects.all() if queryset is None else queryset
    return (
        queryset.exclude(status=Maintenance.Status.CANCELLED)
        .values("vehicle__id", "vehicle__registration_number", "vehicle__brand", "vehicle__model")
        .annotate(total=Sum("cost"), count=Count("id"))
        .order_by("-total")
    )


def cost_by_month(months=12):
    """Dépenses d'entretien des `months` derniers mois (mois sans dépense inclus)."""
    today = timezone.localdate()
    # Premier jour du mois situé (months - 1) mois avant le mois courant
    year, month = divmod(today.year * 12 + today.month - 1 - (months - 1), 12)
    first_month = today.replace(year=year, month=month + 1, day=1)
    rows = (
        Maintenance.objects.exclude(status=Maintenance.Status.CANCELLED)
        .filter(date__gte=first_month, date__lte=today)
        .annotate(month=TruncMonth("date"))
        .values("month")
        .annotate(total=Sum("cost"))
    )
    totals = {row["month"].strftime("%Y-%m"): float(row["total"] or 0) for row in rows}
    result, cursor = [], first_month
    for _ in range(months):
        key = cursor.strftime("%Y-%m")
        result.append((cursor, totals.get(key, 0.0)))
        cursor = (cursor + timedelta(days=32)).replace(day=1)
    return result

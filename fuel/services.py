"""
Logique métier du carburant : enregistrement, consommation et dépenses.

Méthode de calcul de la consommation (méthode « du plein à plein ») :
quand le réservoir est rempli complètement, la quantité versée correspond
exactement au carburant consommé depuis le plein précédent. Donc :

    consommation (L/100 km) = litres du plein / (km actuel - km du plein précédent) × 100
"""
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from vehicles.models import Vehicle

from .models import FuelEntry

ANOMALY_RATIO = Decimal("1.30")  # +30 % par rapport à la moyenne du véhicule
MIN_ENTRIES_FOR_ANOMALY = 3


@transaction.atomic
def save_fuel_entry(entry, user=None):
    """Enregistre le plein et met à jour le compteur du véhicule si nécessaire."""
    if user is not None and entry.created_by_id is None and user.is_authenticated:
        entry.created_by = user
    entry.full_clean()
    entry.save()
    vehicle = Vehicle.objects.select_for_update().get(pk=entry.vehicle_id)
    if entry.mileage > vehicle.mileage:
        vehicle.mileage = entry.mileage
        vehicle.save(update_fields=["mileage", "updated_at"])
    return entry


def entries_with_consumption(vehicle):
    """Liste des pleins d'un véhicule (ordre du compteur) avec distance et consommation calculées."""
    rows, previous = [], None
    for entry in vehicle.fuel_entries.order_by("mileage", "date"):
        entry.distance = entry.mileage - previous.mileage if previous else None
        entry.consumption = None
        if previous and entry.full_tank and entry.distance and entry.distance > 0:
            entry.consumption = (entry.liters / entry.distance * 100).quantize(Decimal("0.1"))
        rows.append(entry)
        previous = entry
    return rows


def vehicle_fuel_summary(vehicle):
    """Synthèse d'un véhicule : litres, montant, distance couverte, consommation moyenne."""
    rows = entries_with_consumption(vehicle)
    measured = [r for r in rows if r.consumption is not None]
    liters = sum((r.liters for r in measured), Decimal(0))
    distance = sum(r.distance for r in measured)
    return {
        "vehicle": vehicle,
        "entries": len(rows),
        "total_liters": sum((r.liters for r in rows), Decimal(0)),
        "total_amount": sum((r.total_amount for r in rows), Decimal(0)),
        "average": (liters / distance * 100).quantize(Decimal("0.1")) if distance else None,
        "last": rows[-1] if rows else None,
        "rows": rows,
    }


def fleet_fuel_summary():
    """Synthèse pour tous les véhicules ayant au moins un plein, triée par montant."""
    vehicles = Vehicle.objects.filter(fuel_entries__isnull=False).distinct()
    summaries = [vehicle_fuel_summary(v) for v in vehicles]
    return sorted(summaries, key=lambda s: s["total_amount"], reverse=True)


def detect_anomalies():
    """
    Pleins dont la consommation dépasse de plus de 30 % la moyenne du véhicule
    (calculée sur ses autres pleins). Utilisé par le moteur d'alertes.
    """
    anomalies = []
    for summary in fleet_fuel_summary():
        measured = [r for r in summary["rows"] if r.consumption is not None]
        if len(measured) < MIN_ENTRIES_FOR_ANOMALY:
            continue
        last = measured[-1]
        others = measured[:-1]
        reference = sum(r.liters for r in others) / sum(r.distance for r in others) * 100
        if last.consumption > reference * ANOMALY_RATIO:
            anomalies.append({"entry": last, "vehicle": summary["vehicle"],
                              "consumption": last.consumption, "reference": reference.quantize(Decimal("0.1"))})
    return anomalies


def total_amount(queryset=None):
    queryset = FuelEntry.objects.all() if queryset is None else queryset
    return queryset.aggregate(total=Sum("total_amount"))["total"] or 0


def cost_by_month(months=12):
    """Dépenses de carburant des `months` derniers mois (mois sans plein inclus)."""
    from maintenance.services import month_range

    month_list = month_range(months)
    rows = (FuelEntry.objects.filter(date__gte=month_list[0], date__lte=timezone.localdate())
            .annotate(month=TruncMonth("date")).values("month").annotate(total=Sum("total_amount")))
    totals = {row["month"].strftime("%Y-%m"): float(row["total"] or 0) for row in rows}
    return [(m, totals.get(m.strftime("%Y-%m"), 0.0)) for m in month_list]


def totals_by_vehicle(queryset):
    return (queryset.values("vehicle__id", "vehicle__registration_number", "vehicle__brand", "vehicle__model")
            .annotate(liters=Sum("liters"), total=Sum("total_amount"), count=Count("id")).order_by("-total"))

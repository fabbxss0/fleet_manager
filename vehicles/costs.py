"""
Coût de revient (coût total de possession) des véhicules.

    Coût d'exploitation = entretiens + carburant + assurances + sinistres (reste à charge)
    Coût total          = prix d'acquisition + coût d'exploitation
    Coût au km          = coût d'exploitation / km parcourus depuis l'acquisition

Un véhicule dont le coût d'exploitation annuel dépasse 30 % de son prix
d'achat est signalé « à étudier » : il peut devenir plus rentable de le remplacer.
"""
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from .models import Vehicle

REVIEW_RATIO = Decimal("0.30")


def _sum(queryset, field):
    return queryset.aggregate(total=Sum(field))["total"] or Decimal(0)


def vehicle_costs(vehicle):
    """Détail des coûts d'un véhicule depuis son acquisition."""
    from claims.services import net_cost_for_vehicle

    maintenance = _sum(vehicle.maintenances.exclude(status="ANNULE"), "cost")
    fuel = _sum(vehicle.fuel_entries.all(), "total_amount")
    insurance = _sum(vehicle.insurances.all(), "premium")
    claims = Decimal(net_cost_for_vehicle(vehicle))
    operating = maintenance + fuel + insurance + claims
    km = max(vehicle.mileage - vehicle.acquisition_mileage, 0)
    days = max((timezone.localdate() - vehicle.acquisition_date).days, 1)
    years = Decimal(days) / Decimal("365.25")
    annual = (operating / years).quantize(Decimal("1")) if years >= Decimal("0.25") else None
    return {
        "vehicle": vehicle,
        "acquisition": vehicle.acquisition_price,
        "maintenance": maintenance, "fuel": fuel, "insurance": insurance, "claims": claims,
        "operating": operating,
        "total": vehicle.acquisition_price + operating,
        "km": km,
        "per_km": (operating / km).quantize(Decimal("1")) if km else None,
        "years": years.quantize(Decimal("0.1")),
        "annual_operating": annual,
        "to_review": bool(annual and vehicle.acquisition_price and annual > vehicle.acquisition_price * REVIEW_RATIO),
    }


def fleet_costs(include_out_of_service=False):
    vehicles = Vehicle.objects.all()
    if not include_out_of_service:
        vehicles = vehicles.exclude(status=Vehicle.Status.OUT_OF_SERVICE)
    rows = [vehicle_costs(v) for v in vehicles]
    return sorted(rows, key=lambda r: r["operating"], reverse=True)


def fleet_totals(rows):
    keys = ("acquisition", "maintenance", "fuel", "insurance", "claims", "operating", "total", "km")
    totals = {k: sum((r[k] for r in rows), Decimal(0)) for k in keys}
    totals["per_km"] = (totals["operating"] / totals["km"]).quantize(Decimal("1")) if totals["km"] else None
    return totals

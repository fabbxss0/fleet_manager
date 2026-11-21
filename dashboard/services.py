"""Calcul des indicateurs du tableau de bord (toutes les valeurs viennent de la base)."""
from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from alerts.models import Alert
from assignments.models import Assignment
from core.models import AppSettings
from drivers.models import Driver
from insurance.models import Insurance
from maintenance import services as maintenance_services
from maintenance.models import Maintenance
from vehicles.models import Vehicle


def _expired_insurance_vehicle_count(today):
    """Véhicules en service dont la dernière assurance est expirée."""
    count = 0
    for vehicle in Vehicle.objects.exclude(status=Vehicle.Status.OUT_OF_SERVICE).prefetch_related("insurances"):
        policies = list(vehicle.insurances.all())
        if policies and max(p.end_date for p in policies) < today:
            count += 1
    return count


def get_kpis():
    today = timezone.localdate()
    status_counts = dict(Vehicle.objects.values_list("status").annotate(n=Count("id")))
    schedules = maintenance_services.get_due_schedules()
    return {
        "total_vehicles": sum(status_counts.values()),
        "available": status_counts.get(Vehicle.Status.AVAILABLE, 0),
        "assigned": status_counts.get(Vehicle.Status.ASSIGNED, 0),
        "in_maintenance": status_counts.get(Vehicle.Status.MAINTENANCE, 0),
        "immobilized": status_counts.get(Vehicle.Status.IMMOBILIZED, 0),
        "out_of_service": status_counts.get(Vehicle.Status.OUT_OF_SERVICE, 0),
        "drivers": Driver.objects.exclude(status=Driver.Status.INACTIVE).count(),
        "active_assignments": Assignment.objects.filter(status=Assignment.Status.ACTIVE).count(),
        "expired_insurances": _expired_insurance_vehicle_count(today),
        "maintenance_due": len(schedules),
        "maintenance_overdue": sum(1 for s in schedules if s["state"] == "overdue"),
        "unread_alerts": Alert.objects.filter(is_resolved=False, is_read=False).count(),
        "year_expenses": maintenance_services.total_cost(Maintenance.objects.filter(date__year=today.year)),
    }


def _choices_dataset(queryset_counts, choices):
    labels_map = dict(choices)
    counts = dict(queryset_counts)
    keys = [k for k, _ in choices if counts.get(k)]
    return {"labels": [labels_map[k] for k in keys], "values": [counts[k] for k in keys], "keys": keys}


def get_chart_data():
    """Données des 5 graphiques Chart.js."""
    by_category = Vehicle.objects.values_list("category").annotate(n=Count("id"))
    by_status = Vehicle.objects.values_list("status").annotate(n=Count("id"))
    monthly = maintenance_services.cost_by_month(12)
    per_vehicle = list(maintenance_services.cost_by_vehicle()[:10])
    alerts_by_priority = Alert.objects.filter(is_resolved=False).values_list("priority").annotate(n=Count("id"))
    priority_counts = dict(alerts_by_priority)
    return {
        "category": _choices_dataset(by_category, Vehicle.Category.choices),
        "status": _choices_dataset(by_status, Vehicle.Status.choices),
        "monthly": {"labels": [m.strftime("%m/%Y") for m, _ in monthly], "values": [t for _, t in monthly]},
        "per_vehicle": {
            "labels": [r["vehicle__registration_number"] for r in per_vehicle],
            "values": [float(r["total"]) for r in per_vehicle],
        },
        "alerts": {
            "labels": [label for _, label in Alert.Priority.choices],
            "values": [priority_counts.get(value, 0) for value, _ in Alert.Priority.choices],
        },
    }


def get_upcoming_deadlines(limit=8):
    """Prochaines échéances (assurances, permis, entretiens) triées par date."""
    today = timezone.localdate()
    horizon = today + timedelta(days=max(AppSettings.load().alert_days_warning, 60))
    items = []
    for ins in Insurance.objects.filter(end_date__gte=today, end_date__lte=horizon).select_related("vehicle"):
        items.append({"date": ins.end_date, "icon": "shield-check", "label": f"Fin d'assurance — {ins.vehicle.registration_number}",
                      "url": ins.get_absolute_url()})
    for driver in Driver.objects.exclude(status=Driver.Status.INACTIVE).filter(
            license_expiry_date__gte=today, license_expiry_date__lte=horizon):
        items.append({"date": driver.license_expiry_date, "icon": "person-vcard",
                      "label": f"Expiration du permis — {driver.full_name}", "url": driver.get_absolute_url()})
    for m in Maintenance.objects.filter(status=Maintenance.Status.DONE, next_date__gte=today,
                                        next_date__lte=horizon).select_related("vehicle"):
        items.append({"date": m.next_date, "icon": "tools",
                      "label": f"{m.get_intervention_type_display()} — {m.vehicle.registration_number}",
                      "url": m.get_absolute_url()})
    for a in Assignment.objects.filter(status=Assignment.Status.ACTIVE, expected_end_date__gte=today,
                                       expected_end_date__lte=horizon).select_related("vehicle"):
        items.append({"date": a.expected_end_date, "icon": "arrow-left-right",
                      "label": f"Retour prévu — {a.vehicle.registration_number}", "url": a.get_absolute_url()})
    for item in items:
        item["days"] = (item["date"] - today).days
    return sorted(items, key=lambda i: i["date"])[:limit]

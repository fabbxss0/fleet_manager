from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from alerts.models import Alert
from assignments.models import Assignment
from core.permissions import role_required, staff_required
from maintenance.models import Maintenance

from . import services


@login_required
def home(request):
    """Page d'accueil : tableau de bord pour la gestion, espace personnel pour un conducteur."""
    if request.user.is_driver:
        return redirect("dashboard:driver_space")
    return dashboard(request)


@staff_required
def dashboard(request):
    context = {
        "page_title": "Tableau de bord",
        "kpis": services.get_kpis(),
        "charts": services.get_chart_data(),
        "latest_assignments": Assignment.objects.select_related("vehicle", "driver")[:6],
        "latest_maintenances": Maintenance.objects.select_related("vehicle")[:6],
        "urgent_alerts": Alert.objects.filter(is_resolved=False, priority__gte=Alert.Priority.URGENT)
        .order_by("-priority", "-created_at")[:6],
        "deadlines": services.get_upcoming_deadlines(),
    }
    return render(request, "dashboard/dashboard.html", context)


@role_required("CONDUCTEUR")
def driver_space(request):
    """Espace conducteur : uniquement ses propres informations."""
    driver = getattr(request.user, "driver_profile", None)
    if driver is None:
        messages.warning(request, "Votre compte n'est rattaché à aucune fiche conducteur. Contactez l'administrateur.")
        return render(request, "dashboard/driver_space.html", {"page_title": "Mon espace", "driver": None})
    current = driver.current_assignment
    vehicle = current.vehicle if current else None
    context = {
        "page_title": "Mon espace", "driver": driver, "current": current, "vehicle": vehicle,
        "history": driver.assignments.select_related("vehicle"),
    }
    if vehicle:
        context["insurance"] = vehicle.current_insurance
        context["my_fuel_entries"] = driver.fuel_entries.select_related("vehicle")[:5]
        context["last_maintenances"] = vehicle.maintenances.filter(status=Maintenance.Status.DONE)[:5]
        context["next_maintenance"] = vehicle.maintenances.filter(
            status=Maintenance.Status.DONE, next_date__isnull=False).order_by("-date").first()
    return render(request, "dashboard/driver_space.html", context)

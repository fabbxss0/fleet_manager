from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Count, ProtectedError, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from core.filters import filter_period, parse_int
from core.permissions import StaffRequiredMixin, staff_required
from core.views_mixins import FilteredListMixin, PageTitleMixin
from vehicles.models import Vehicle

from . import services
from .forms import MaintenanceForm
from .models import Maintenance


class MaintenanceListView(StaffRequiredMixin, PageTitleMixin, FilteredListMixin, ListView):
    model = Maintenance
    template_name = "maintenance/maintenance_list.html"
    page_title = "Entretiens et réparations"
    search_fields = ("vehicle__registration_number", "provider", "description")
    filter_fields = ("intervention_type", "status", "vehicle")

    def get_queryset(self):
        queryset = super().get_queryset().select_related("vehicle")
        queryset = filter_period(queryset, self.request.GET)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["types"] = Maintenance.InterventionType.choices
        context["statuses"] = Maintenance.Status.choices
        context["vehicles"] = Vehicle.objects.all()
        context["filtered_total"] = services.total_cost(self.object_list)
        context["du"], context["au"] = self.request.GET.get("du", ""), self.request.GET.get("au", "")
        return context


class MaintenanceDetailView(StaffRequiredMixin, PageTitleMixin, DetailView):
    model = Maintenance
    template_name = "maintenance/maintenance_detail.html"
    page_title = "Détail de l'intervention"


class MaintenanceSaveMixin:
    """Utilise le service métier pour enregistrer et synchroniser le véhicule."""

    def form_valid(self, form):
        try:
            self.object = services.save_maintenance(form.save(commit=False))
        except ValidationError as exc:
            for field, errors in exc.message_dict.items():
                form.add_error(field if field in form.fields else None, errors)
            return self.form_invalid(form)
        messages.success(self.request, self.success_message)
        return redirect(self.object.get_absolute_url())

    def form_invalid(self, form):
        messages.error(self.request, "Le formulaire contient des erreurs. Veuillez les corriger.")
        return super().form_invalid(form)


class MaintenanceCreateView(StaffRequiredMixin, PageTitleMixin, MaintenanceSaveMixin, CreateView):
    model = Maintenance
    form_class = MaintenanceForm
    template_name = "maintenance/maintenance_form.html"
    page_title = "Nouvel entretien"
    success_message = "L'intervention a été enregistrée."

    def get_initial(self):
        initial = super().get_initial()
        vehicle_id = parse_int(self.request.GET.get("vehicle"))
        if vehicle_id:
            vehicle = Vehicle.objects.filter(pk=vehicle_id).first()
            if vehicle:
                initial.update(vehicle=vehicle, mileage=vehicle.mileage)
        if self.request.GET.get("type"):
            initial["intervention_type"] = self.request.GET["type"]
        return initial


class MaintenanceUpdateView(StaffRequiredMixin, PageTitleMixin, MaintenanceSaveMixin, UpdateView):
    model = Maintenance
    form_class = MaintenanceForm
    template_name = "maintenance/maintenance_form.html"
    page_title = "Modifier l'entretien"
    success_message = "L'intervention a été mise à jour."


@staff_required
@require_POST
def maintenance_delete(request, pk):
    maintenance = get_object_or_404(Maintenance, pk=pk)
    vehicle = maintenance.vehicle
    try:
        maintenance.delete()
    except ProtectedError:
        messages.error(request, "Suppression impossible.")
        return redirect(maintenance.get_absolute_url())
    vehicle.refresh_status()
    messages.success(request, "L'intervention a été supprimée.")
    return redirect(reverse_lazy("maintenance:list"))


@staff_required
def maintenance_due(request):
    """Véhicules nécessitant un entretien (périodicité par date ou kilométrage)."""
    schedules = services.get_due_schedules()
    in_progress = Maintenance.objects.filter(
        status__in=[Maintenance.Status.IN_PROGRESS, Maintenance.Status.PLANNED]).select_related("vehicle")
    return render(request, "maintenance/maintenance_due.html", {
        "schedules": schedules, "in_progress": in_progress, "page_title": "Entretiens à prévoir",
        "overdue_count": sum(1 for s in schedules if s["state"] == "overdue"),
    })


@staff_required
def maintenance_expenses(request):
    """Dépenses d'entretien : total, par véhicule et par mois."""
    queryset = Maintenance.objects.all()
    du, au = request.GET.get("du", ""), request.GET.get("au", "")
    queryset = filter_period(queryset, request.GET)
    by_vehicle = list(services.cost_by_vehicle(queryset))
    by_type = (
        queryset.exclude(status=Maintenance.Status.CANCELLED).values("intervention_type")
        .annotate(total=Sum("cost"), count=Count("id")).order_by("-total")
    )
    type_labels = dict(Maintenance.InterventionType.choices)
    monthly = services.cost_by_month(12)
    return render(request, "maintenance/maintenance_expenses.html", {
        "page_title": "Dépenses d'entretien", "du": du, "au": au,
        "total": services.total_cost(queryset),
        "by_vehicle": by_vehicle,
        "by_type": [{"label": type_labels[r["intervention_type"]], **r} for r in by_type],
        "chart_months": [m.strftime("%m/%Y") for m, _ in monthly],
        "chart_totals": [t for _, t in monthly],
    })

from django.db.models import Count, Q
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from core.permissions import StaffRequiredMixin
from core.views_mixins import FilteredListMixin, FormMessagesMixin, PageTitleMixin, SafeDeleteView

from .forms import VehicleForm
from .models import Vehicle


class VehicleListView(StaffRequiredMixin, PageTitleMixin, FilteredListMixin, ListView):
    model = Vehicle
    template_name = "vehicles/vehicle_list.html"
    page_title = "Véhicules"
    search_fields = ("registration_number", "brand", "model")
    filter_fields = ("category", "status", "fuel_type")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categories"] = Vehicle.Category.choices
        context["statuses"] = Vehicle.Status.choices
        context["fuels"] = Vehicle.Fuel.choices
        counts = Vehicle.objects.aggregate(
            total=Count("id"), **{s.value: Count("id", filter=Q(status=s.value)) for s in Vehicle.Status}
        )
        context["status_counts"] = counts
        return context


class VehicleDetailView(StaffRequiredMixin, PageTitleMixin, DetailView):
    model = Vehicle
    template_name = "vehicles/vehicle_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        vehicle = self.object
        context["page_title"] = vehicle.registration_number
        context["assignments"] = vehicle.assignments.select_related("driver")[:50]
        context["maintenances"] = vehicle.maintenances.all()[:50]
        context["insurances"] = vehicle.insurances.all()
        context["alerts"] = vehicle.alerts.filter(is_resolved=False)
        from fuel.services import vehicle_fuel_summary

        context["fuel"] = vehicle_fuel_summary(vehicle)
        context["has_history"] = (
            vehicle.assignments.exists() or vehicle.maintenances.exists() or vehicle.insurances.exists()
            or vehicle.fuel_entries.exists()
        )
        # Chronologie unifiée (historique du véhicule)
        timeline = []
        for a in context["assignments"]:
            timeline.append({"date": a.start_date, "icon": "arrow-left-right", "color": "primary",
                             "title": f"Affectation à {a.driver.full_name}", "text": a.purpose, "url": a.get_absolute_url()})
            if a.actual_return_date:
                timeline.append({"date": a.actual_return_date, "icon": "box-arrow-in-left", "color": "success",
                                 "title": "Retour du véhicule", "text": f"{a.distance} km parcourus", "url": a.get_absolute_url()})
        for m in context["maintenances"]:
            timeline.append({"date": m.date, "icon": "tools", "color": "warning",
                             "title": m.get_intervention_type_display(), "text": m.provider, "url": m.get_absolute_url()})
        for i in context["insurances"]:
            timeline.append({"date": i.start_date, "icon": "shield-check", "color": "info",
                             "title": f"Assurance {i.company}", "text": i.get_insurance_type_display(), "url": i.get_absolute_url()})
        context["timeline"] = sorted(timeline, key=lambda e: e["date"], reverse=True)[:30]
        return context


class VehicleCreateView(StaffRequiredMixin, PageTitleMixin, FormMessagesMixin, CreateView):
    model = Vehicle
    form_class = VehicleForm
    template_name = "vehicles/vehicle_form.html"
    page_title = "Nouveau véhicule"
    success_message = "Le véhicule a été ajouté au parc."


class VehicleUpdateView(StaffRequiredMixin, PageTitleMixin, FormMessagesMixin, UpdateView):
    model = Vehicle
    form_class = VehicleForm
    template_name = "vehicles/vehicle_form.html"
    page_title = "Modifier le véhicule"
    success_message = "Le véhicule a été mis à jour."

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.object.status == Vehicle.Status.AVAILABLE:
            self.object.refresh_status()  # ex. sortie d'immobilisation pendant un entretien en cours
        return response


class VehicleDeleteView(StaffRequiredMixin, SafeDeleteView):
    model = Vehicle
    success_url = reverse_lazy("vehicles:list")
    success_message = "Le véhicule a été supprimé."
    protected_message = (
        "Suppression impossible : ce véhicule possède un historique (affectations, entretiens, assurances ou carburant). "
        "Passez-le plutôt au statut « Hors service » pour conserver l'historique."
    )

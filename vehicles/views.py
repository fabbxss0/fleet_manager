from django.db.models import Count, Q
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from core.permissions import StaffRequiredMixin, staff_required
from core.views_mixins import FilteredListMixin, FormMessagesMixin, PageTitleMixin, SafeDeleteView

from . import costs, importer
from .forms import VehicleForm
from .models import Vehicle


class VehicleListView(StaffRequiredMixin, PageTitleMixin, FilteredListMixin, ListView):
    model = Vehicle
    template_name = "vehicles/vehicle_list.html"
    page_title = "Véhicules"
    search_fields = ("registration_number", "brand", "model", "department", "registration_card_number")
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


@staff_required
def vehicle_import_template(request):
    response = HttpResponse(importer.build_template(),
                            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = 'attachment; filename="modele_import_vehicules.xlsx"'
    return response


@staff_required
def vehicle_import(request):
    """Import Excel en deux temps : vérification, puis enregistrement (tout ou rien)."""
    context = {"page_title": "Importer des véhicules", "max_rows": importer.MAX_ROWS}
    if request.method == "POST":
        uploaded = request.FILES.get("fichier")
        if not uploaded:
            messages.error(request, "Choisissez un fichier Excel.")
            return render(request, "vehicles/vehicle_import.html", context)
        rows, error = importer.parse_workbook(uploaded)
        if error:
            messages.error(request, error)
            return render(request, "vehicles/vehicle_import.html", context)
        error_count = sum(1 for r in rows if r["errors"])
        context.update(rows=rows, error_count=error_count, valid_count=len(rows) - error_count,
                       file_name=uploaded.name)
        if error_count:
            messages.error(request, f"{error_count} ligne(s) contiennent des erreurs : aucun véhicule n'a été importé.")
        elif request.POST.get("action") == "importer":
            created = importer.import_rows(rows)
            messages.success(request, f"{len(created)} véhicule(s) importé(s) avec succès.")
            return redirect("vehicles:list")
        else:
            context["ready"] = True
            messages.info(request, f"Fichier valide : {len(rows)} véhicule(s) prêt(s). Sélectionnez à nouveau le "
                                   "fichier et cliquez sur « Importer » pour confirmer.")
    return render(request, "vehicles/vehicle_import.html", context)


@staff_required
def vehicle_costs_view(request):
    """Coût de revient de chaque véhicule du parc."""
    show_all = request.GET.get("tous") == "1"
    rows = costs.fleet_costs(include_out_of_service=show_all)
    return render(request, "vehicles/vehicle_costs.html", {
        "page_title": "Coût de revient des véhicules", "rows": rows, "totals": costs.fleet_totals(rows),
        "show_all": show_all, "review_ratio": int(costs.REVIEW_RATIO * 100),
        "chart": {
            "labels": [r["vehicle"].registration_number for r in rows[:10]],
            "series": [
                {"label": label, "values": [float(r[key]) for r in rows[:10]], "color": color}
                for key, label, color in (("maintenance", "Entretien", "#2563eb"), ("fuel", "Carburant", "#0284c7"),
                                          ("insurance", "Assurance", "#16a34a"), ("claims", "Sinistres", "#ea580c"))
            ],
        },
    })


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
        context["claims"] = vehicle.claims.select_related("driver")
        context["costs"] = costs.vehicle_costs(vehicle)
        context["has_history"] = (
            vehicle.assignments.exists() or vehicle.maintenances.exists() or vehicle.insurances.exists()
            or vehicle.fuel_entries.exists() or vehicle.claims.exists()
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

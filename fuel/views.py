from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, ListView, UpdateView

from core.filters import filter_period, parse_int
from core.permissions import StaffRequiredMixin, role_required, staff_required
from core.views_mixins import FilteredListMixin, PageTitleMixin
from vehicles.models import Vehicle

from . import services
from .forms import DriverFuelEntryForm, FuelEntryForm
from .models import FuelEntry


class FuelListView(StaffRequiredMixin, PageTitleMixin, FilteredListMixin, ListView):
    model = FuelEntry
    template_name = "fuel/fuel_list.html"
    page_title = "Carburant"
    search_fields = ("vehicle__registration_number", "station", "driver__last_name")
    filter_fields = ("vehicle",)

    def get_queryset(self):
        queryset = super().get_queryset().select_related("vehicle", "driver")
        queryset = filter_period(queryset, self.request.GET)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = self.object_list
        context["vehicles"] = Vehicle.objects.filter(fuel_entries__isnull=False).distinct()
        context["filtered_total"] = services.total_amount(qs)
        context["filtered_liters"] = sum(e.liters for e in qs)
        context["du"], context["au"] = self.request.GET.get("du", ""), self.request.GET.get("au", "")
        vehicle_id = self.request.GET.get("vehicle")
        if vehicle_id and vehicle_id.isdigit():
            vehicle = Vehicle.objects.filter(pk=vehicle_id).first()
            if vehicle:
                context["summary"] = services.vehicle_fuel_summary(vehicle)
        return context


class FuelSaveMixin:
    def form_valid(self, form):
        try:
            services.save_fuel_entry(form.save(commit=False), self.request.user)
        except ValidationError as exc:
            for field, errors in exc.message_dict.items():
                form.add_error(field if field in form.fields else None, errors)
            return self.form_invalid(form)
        messages.success(self.request, self.success_message)
        return redirect("fuel:list")

    def form_invalid(self, form):
        messages.error(self.request, "Le formulaire contient des erreurs. Veuillez les corriger.")
        return super().form_invalid(form)


class FuelCreateView(StaffRequiredMixin, PageTitleMixin, FuelSaveMixin, CreateView):
    model = FuelEntry
    form_class = FuelEntryForm
    template_name = "fuel/fuel_form.html"
    page_title = "Enregistrer un plein"
    success_message = "Le plein a été enregistré."

    def get_initial(self):
        initial = super().get_initial()
        vehicle = Vehicle.objects.filter(pk=parse_int(self.request.GET.get("vehicle")) or 0).first()
        if vehicle:
            initial["vehicle"] = vehicle
            initial["mileage"] = vehicle.mileage
            current = vehicle.current_assignment
            if current:
                initial["driver"] = current.driver
        return initial


class FuelUpdateView(StaffRequiredMixin, PageTitleMixin, FuelSaveMixin, UpdateView):
    model = FuelEntry
    form_class = FuelEntryForm
    template_name = "fuel/fuel_form.html"
    page_title = "Modifier le plein"
    success_message = "Le plein a été mis à jour."


@staff_required
@require_POST
def fuel_delete(request, pk):
    entry = get_object_or_404(FuelEntry, pk=pk)
    entry.delete()
    messages.success(request, "Le plein a été supprimé.")
    return redirect("fuel:list")


@staff_required
def fuel_stats(request):
    """Consommation moyenne par véhicule et dépenses mensuelles."""
    summaries = services.fleet_fuel_summary()
    monthly = services.cost_by_month(12)
    anomalies = services.detect_anomalies()
    return render(request, "fuel/fuel_stats.html", {
        "page_title": "Consommation de carburant",
        "summaries": summaries, "anomalies": anomalies,
        "total": services.total_amount(),
        "chart_months": [m.strftime("%m/%Y") for m, _ in monthly],
        "chart_totals": [t for _, t in monthly],
        "chart_vehicles": [s["vehicle"].registration_number for s in summaries if s["average"] is not None],
        "chart_averages": [float(s["average"]) for s in summaries if s["average"] is not None],
    })


@role_required("CONDUCTEUR")
def driver_fuel_declare(request):
    """Le conducteur déclare un plein pour le véhicule qui lui est actuellement affecté."""
    driver = getattr(request.user, "driver_profile", None)
    current = driver.current_assignment if driver else None
    if current is None:
        messages.error(request, "Aucun véhicule ne vous est affecté : impossible de déclarer un plein.")
        return redirect("dashboard:driver_space")
    entry = FuelEntry(vehicle=current.vehicle, driver=driver)
    form = DriverFuelEntryForm(request.POST or None, request.FILES or None, instance=entry,
                               initial={"mileage": current.vehicle.mileage})
    if request.method == "POST":
        if form.is_valid():
            try:
                services.save_fuel_entry(form.save(commit=False), request.user)
            except ValidationError as exc:
                for field, errors in exc.message_dict.items():
                    form.add_error(field if field in form.fields else None, errors)
            else:
                messages.success(request, "Votre plein a été enregistré. Merci !")
                return redirect("dashboard:driver_space")
        messages.error(request, "Le formulaire contient des erreurs. Veuillez les corriger.")
    return render(request, "fuel/fuel_form.html", {
        "form": form, "page_title": "Déclarer un plein", "driver_vehicle": current.vehicle,
    })

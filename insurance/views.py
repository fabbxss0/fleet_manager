from datetime import timedelta

from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from core.models import AppSettings
from core.permissions import StaffRequiredMixin
from core.views_mixins import FilteredListMixin, FormMessagesMixin, PageTitleMixin, SafeDeleteView
from vehicles.models import Vehicle

from .forms import InsuranceForm
from .models import Insurance


class InsuranceListView(StaffRequiredMixin, PageTitleMixin, FilteredListMixin, ListView):
    model = Insurance
    template_name = "insurance/insurance_list.html"
    page_title = "Assurances"
    search_fields = ("policy_number", "company", "vehicle__registration_number")
    filter_fields = ("insurance_type", "vehicle")

    def get_queryset(self):
        queryset = super().get_queryset().select_related("vehicle")
        today = timezone.localdate()
        warning = today + timedelta(days=AppSettings.load().alert_days_warning)
        state = self.request.GET.get("etat")
        if state == "expiree":
            queryset = queryset.filter(end_date__lt=today)
        elif state == "bientot":
            queryset = queryset.filter(end_date__gte=today, end_date__lte=warning)
        elif state == "valide":
            queryset = queryset.filter(start_date__lte=today, end_date__gt=warning)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        warning = today + timedelta(days=AppSettings.load().alert_days_warning)
        context["etat"] = self.request.GET.get("etat", "")
        context["types"] = Insurance.InsuranceType.choices
        context["vehicles"] = Vehicle.objects.all()
        context["counts"] = {
            "all": Insurance.objects.count(),
            "expired": Insurance.objects.filter(end_date__lt=today).count(),
            "expiring": Insurance.objects.filter(end_date__gte=today, end_date__lte=warning).count(),
        }
        # Véhicules en service sans aucune assurance valide aujourd'hui
        context["uninsured"] = Vehicle.objects.exclude(status=Vehicle.Status.OUT_OF_SERVICE).exclude(
            insurances__start_date__lte=today, insurances__end_date__gte=today)
        return context


class InsuranceDetailView(StaffRequiredMixin, PageTitleMixin, DetailView):
    model = Insurance
    template_name = "insurance/insurance_detail.html"
    page_title = "Détail de l'assurance"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["history"] = self.object.vehicle.insurances.exclude(pk=self.object.pk)
        return context


class InsuranceCreateView(StaffRequiredMixin, PageTitleMixin, FormMessagesMixin, CreateView):
    model = Insurance
    form_class = InsuranceForm
    template_name = "insurance/insurance_form.html"
    page_title = "Nouvelle assurance"
    success_message = "L'assurance a été enregistrée."

    def get_initial(self):
        initial = super().get_initial()
        if self.request.GET.get("vehicle"):
            initial["vehicle"] = self.request.GET["vehicle"]
        return initial


class InsuranceUpdateView(StaffRequiredMixin, PageTitleMixin, FormMessagesMixin, UpdateView):
    model = Insurance
    form_class = InsuranceForm
    template_name = "insurance/insurance_form.html"
    page_title = "Modifier l'assurance"
    success_message = "L'assurance a été mise à jour."


class InsuranceDeleteView(StaffRequiredMixin, SafeDeleteView):
    model = Insurance
    success_url = reverse_lazy("insurance:list")
    success_message = "L'assurance a été supprimée."

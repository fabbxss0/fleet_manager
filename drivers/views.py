from datetime import timedelta

from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from core.models import AppSettings
from core.permissions import StaffRequiredMixin
from core.views_mixins import FilteredListMixin, FormMessagesMixin, PageTitleMixin, SafeDeleteView

from .forms import DriverForm
from .models import Driver


class DriverListView(StaffRequiredMixin, PageTitleMixin, FilteredListMixin, ListView):
    model = Driver
    template_name = "drivers/driver_list.html"
    page_title = "Conducteurs"
    search_fields = ("last_name", "first_name", "license_number", "phone", "email")
    filter_fields = ("status", "license_category")

    def get_queryset(self):
        queryset = super().get_queryset().prefetch_related("assignments__vehicle")
        license_filter = self.request.GET.get("permis")
        today = timezone.localdate()
        warning_days = AppSettings.load().alert_days_warning
        if license_filter == "expire":
            queryset = queryset.filter(license_expiry_date__lt=today)
        elif license_filter == "bientot":
            queryset = queryset.filter(license_expiry_date__gte=today,
                                       license_expiry_date__lte=today + timedelta(days=warning_days))
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["statuses"] = Driver.Status.choices
        context["license_categories"] = Driver.LicenseCategory.choices
        context["permis"] = self.request.GET.get("permis", "")
        context["warning_days"] = AppSettings.load().alert_days_warning
        return context


class DriverDetailView(StaffRequiredMixin, PageTitleMixin, DetailView):
    model = Driver
    template_name = "drivers/driver_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = self.object.full_name
        assignments = self.object.assignments.select_related("vehicle")
        context["assignments"] = assignments
        context["total_distance"] = sum(a.distance or 0 for a in assignments)
        context["alerts"] = self.object.alerts.filter(is_resolved=False)
        context["warning_days"] = AppSettings.load().alert_days_warning
        return context


class DriverCreateView(StaffRequiredMixin, PageTitleMixin, FormMessagesMixin, CreateView):
    model = Driver
    form_class = DriverForm
    template_name = "drivers/driver_form.html"
    page_title = "Nouveau conducteur"
    success_message = "Le conducteur a été enregistré."


class DriverUpdateView(StaffRequiredMixin, PageTitleMixin, FormMessagesMixin, UpdateView):
    model = Driver
    form_class = DriverForm
    template_name = "drivers/driver_form.html"
    page_title = "Modifier le conducteur"
    success_message = "Les informations du conducteur ont été mises à jour."


class DriverDeleteView(StaffRequiredMixin, SafeDeleteView):
    model = Driver
    success_url = reverse_lazy("drivers:list")
    success_message = "Le conducteur a été supprimé."
    protected_message = (
        "Suppression impossible : ce conducteur possède un historique d'affectations. "
        "Passez-le plutôt au statut « Inactif »."
    )

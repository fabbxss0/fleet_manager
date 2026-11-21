from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from core.permissions import StaffRequiredMixin, staff_required
from core.views_mixins import FilteredListMixin, PageTitleMixin
from vehicles.models import Vehicle

from . import services
from .forms import ClaimForm
from .models import Claim


class ClaimListView(StaffRequiredMixin, PageTitleMixin, FilteredListMixin, ListView):
    model = Claim
    template_name = "claims/claim_list.html"
    page_title = "Sinistres et accidents"
    search_fields = ("vehicle__registration_number", "location", "description", "driver__last_name",
                     "police_report_number", "insurance_claim_number")
    filter_fields = ("status", "claim_type", "insurance_status", "vehicle")

    def get_queryset(self):
        queryset = super().get_queryset().select_related("vehicle", "driver")
        if self.request.GET.get("du"):
            queryset = queryset.filter(date__gte=self.request.GET["du"])
        if self.request.GET.get("au"):
            queryset = queryset.filter(date__lte=self.request.GET["au"])
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            statuses=Claim.Status.choices, types=Claim.ClaimType.choices,
            insurance_statuses=Claim.InsuranceStatus.choices,
            vehicles=Vehicle.objects.filter(claims__isnull=False).distinct(),
            totals=services.totals(self.object_list), du=self.request.GET.get("du", ""), au=self.request.GET.get("au", ""),
        )
        return context


class ClaimDetailView(StaffRequiredMixin, PageTitleMixin, DetailView):
    model = Claim
    template_name = "claims/claim_detail.html"
    page_title = "Détail du sinistre"


class ClaimSaveMixin:
    def form_valid(self, form):
        immobilize = form.cleaned_data.get("immobilize", False)
        try:
            self.object = services.save_claim(form.save(commit=False), self.request.user, immobilize=immobilize)
        except ValidationError as exc:
            for field, errors in exc.message_dict.items():
                form.add_error(field if field in form.fields else None, errors)
            return self.form_invalid(form)
        messages.success(self.request, self.success_message)
        if immobilize:
            messages.info(self.request, f"Le véhicule {self.object.vehicle.registration_number} a été immobilisé.")
        return redirect(self.object.get_absolute_url())

    def form_invalid(self, form):
        messages.error(self.request, "Le formulaire contient des erreurs. Veuillez les corriger.")
        return super().form_invalid(form)


class ClaimCreateView(StaffRequiredMixin, PageTitleMixin, ClaimSaveMixin, CreateView):
    model = Claim
    form_class = ClaimForm
    template_name = "claims/claim_form.html"
    page_title = "Déclarer un sinistre"
    success_message = "Le sinistre a été enregistré."

    def get_initial(self):
        initial = super().get_initial()
        for key in ("vehicle", "driver", "assignment"):
            if self.request.GET.get(key):
                initial[key] = self.request.GET[key]
        return initial

    def form_valid(self, form):
        assignment_id = self.request.GET.get("assignment")
        if assignment_id and assignment_id.isdigit():
            form.instance.assignment_id = int(assignment_id)
        return super().form_valid(form)


class ClaimUpdateView(StaffRequiredMixin, PageTitleMixin, ClaimSaveMixin, UpdateView):
    model = Claim
    form_class = ClaimForm
    template_name = "claims/claim_form.html"
    page_title = "Modifier le sinistre"
    success_message = "Le sinistre a été mis à jour."


@staff_required
@require_POST
def claim_delete(request, pk):
    claim = get_object_or_404(Claim, pk=pk)
    claim.delete()
    messages.success(request, "Le sinistre a été supprimé.")
    return redirect("claims:list")

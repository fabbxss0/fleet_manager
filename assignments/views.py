from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from core.permissions import StaffRequiredMixin, staff_required
from core.views_mixins import FilteredListMixin, FormMessagesMixin, PageTitleMixin

from . import services
from .forms import AssignmentCreateForm, AssignmentReturnForm, AssignmentUpdateForm
from .models import Assignment


class AssignmentListView(StaffRequiredMixin, PageTitleMixin, FilteredListMixin, ListView):
    model = Assignment
    template_name = "assignments/assignment_list.html"
    page_title = "Affectations"
    search_fields = ("vehicle__registration_number", "driver__last_name", "driver__first_name", "destination", "purpose")
    filter_fields = ("status",)

    def get_queryset(self):
        queryset = super().get_queryset().select_related("vehicle", "driver")
        if self.request.GET.get("retard") == "1":
            queryset = queryset.filter(status=Assignment.Status.ACTIVE, expected_end_date__lt=timezone.localdate())
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["statuses"] = Assignment.Status.choices
        context["active_count"] = Assignment.objects.filter(status=Assignment.Status.ACTIVE).count()
        context["overdue_count"] = Assignment.objects.filter(
            status=Assignment.Status.ACTIVE, expected_end_date__lt=timezone.localdate()).count()
        return context


class AssignmentDetailView(StaffRequiredMixin, PageTitleMixin, DetailView):
    model = Assignment
    template_name = "assignments/assignment_detail.html"
    page_title = "Détail de l'affectation"


class AssignmentCreateView(StaffRequiredMixin, PageTitleMixin, CreateView):
    model = Assignment
    form_class = AssignmentCreateForm
    template_name = "assignments/assignment_form.html"
    page_title = "Nouvelle affectation"

    def get_initial(self):
        initial = super().get_initial()
        for key in ("vehicle", "driver"):
            if self.request.GET.get(key):
                initial[key] = self.request.GET[key]
        return initial

    def form_valid(self, form):
        try:
            self.object = services.create_assignment(form.save(commit=False))
        except ValidationError as exc:
            for field, errors in exc.message_dict.items():
                form.add_error(field if field in form.fields else None, errors)
            return self.form_invalid(form)
        messages.success(self.request, f"Le véhicule {self.object.vehicle.registration_number} a été affecté "
                                       f"à {self.object.driver.full_name}.")
        return redirect(self.object.get_absolute_url())

    def form_invalid(self, form):
        messages.error(self.request, "L'affectation n'a pas pu être enregistrée. Vérifiez les champs signalés.")
        return super().form_invalid(form)


class AssignmentUpdateView(StaffRequiredMixin, PageTitleMixin, FormMessagesMixin, UpdateView):
    model = Assignment
    form_class = AssignmentUpdateForm
    template_name = "assignments/assignment_form.html"
    page_title = "Modifier l'affectation"
    success_message = "Affectation mise à jour."


@staff_required
def assignment_planning(request):
    """Planning mensuel : qui utilise quel véhicule, et quand."""
    from vehicles.models import Vehicle

    from .planning import build_planning, parse_month

    category = request.GET.get("category", "")
    planning = build_planning(parse_month(request.GET.get("mois")), category)
    return render(request, "assignments/planning.html", {
        "page_title": "Planning du parc", "planning": planning, "category": category,
        "categories": Vehicle.Category.choices,
    })


@staff_required
def assignment_return(request, pk):
    """Enregistrement du retour du véhicule (clôture de l'affectation)."""
    assignment = get_object_or_404(Assignment.objects.select_related("vehicle", "driver"), pk=pk)
    if not assignment.is_active:
        messages.warning(request, "Cette affectation est déjà clôturée.")
        return redirect(assignment.get_absolute_url())
    form = AssignmentReturnForm(request.POST or None, assignment=assignment)
    if request.method == "POST":
        if form.is_valid():
            try:
                cd = form.cleaned_data
                services.close_assignment(assignment, cd["return_date"], cd["return_mileage"], cd["notes"],
                                          fuel_level=cd["return_fuel_level"], condition=cd["return_condition"],
                                          damage_notes=cd["damage_notes"])
            except ValidationError as exc:
                form.add_error(None, exc.messages)
            else:
                messages.success(request, f"Retour enregistré. Statut du véhicule : "
                                          f"{assignment.vehicle.get_status_display()}.")
                if cd["return_condition"] != "RAS":
                    messages.warning(request, "Des dommages ont été signalés : pensez à déclarer un sinistre.")
                return redirect(assignment.get_absolute_url())
        messages.error(request, "Le retour n'a pas pu être enregistré. Vérifiez les champs signalés.")
    return render(request, "assignments/assignment_return.html", {
        "form": form, "assignment": assignment, "page_title": "Retour du véhicule",
    })


@staff_required
@require_POST
def assignment_cancel(request, pk):
    assignment = get_object_or_404(Assignment, pk=pk)
    try:
        services.cancel_assignment(assignment)
        messages.success(request, "L'affectation a été annulée et le véhicule libéré.")
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    return redirect(assignment.get_absolute_url())

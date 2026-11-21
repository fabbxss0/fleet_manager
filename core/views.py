"""Vues transversales : recherche globale, paramètres, fichiers protégés, erreurs."""
from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views.static import serve

from assignments.models import Assignment
from drivers.models import Driver
from insurance.models import Insurance
from vehicles.models import Vehicle

from .forms import BootstrapFormMixin
from .models import AppSettings
from .permissions import staff_required


@login_required
def protected_media(request, path):
    """
    Sert les fichiers téléversés (photos, factures, attestations) uniquement aux
    utilisateurs connectés. En production, cette tâche serait confiée au
    serveur web (ex. X-Accel-Redirect avec Nginx).
    """
    return serve(request, path, document_root=settings.MEDIA_ROOT)


@staff_required
def global_search(request):
    """Recherche transversale depuis la barre supérieure."""
    query = request.GET.get("q", "").strip()
    results = {}
    if len(query) >= 2:
        results = {
            "vehicles": Vehicle.objects.filter(
                Q(registration_number__icontains=query) | Q(brand__icontains=query)
                | Q(model__icontains=query) | Q(chassis_number__icontains=query)
            )[:10],
            "drivers": Driver.objects.filter(
                Q(last_name__icontains=query) | Q(first_name__icontains=query)
                | Q(license_number__icontains=query) | Q(phone__icontains=query)
            )[:10],
            "assignments": Assignment.objects.select_related("vehicle", "driver").filter(
                Q(vehicle__registration_number__icontains=query) | Q(driver__last_name__icontains=query)
                | Q(destination__icontains=query) | Q(purpose__icontains=query)
            )[:10],
            "insurances": Insurance.objects.select_related("vehicle").filter(
                Q(policy_number__icontains=query) | Q(company__icontains=query)
                | Q(vehicle__registration_number__icontains=query)
            )[:10],
        }
    total = sum(len(v) for v in results.values())
    return render(request, "core/search.html", {
        "query": query, "results": results, "total": total, "page_title": "Recherche",
    })


class AppSettingsForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = AppSettings
        fields = [
            "organization_name", "alert_days_warning", "alert_days_urgent",
            "maintenance_days_threshold", "maintenance_km_threshold", "technical_control_days",
        ]

    def clean(self):
        data = super().clean()
        if data.get("alert_days_urgent") and data.get("alert_days_warning") and \
                data["alert_days_urgent"] >= data["alert_days_warning"]:
            self.add_error("alert_days_urgent", "Le seuil urgent doit être inférieur au seuil d'alerte.")
        return data


@login_required
def settings_view(request):
    """Paramètres : modifiables par l'administrateur, consultables par les autres."""
    app_settings = AppSettings.load()
    can_edit = request.user.is_admin
    form = AppSettingsForm(request.POST or None, instance=app_settings)
    if request.method == "POST":
        if not can_edit:
            messages.error(request, "Seul un administrateur peut modifier les paramètres.")
            return redirect("core:settings")
        if form.is_valid():
            form.save()
            from alerts.services import generate_alerts

            generate_alerts()
            messages.success(request, "Paramètres enregistrés. Les alertes ont été recalculées.")
            return redirect("core:settings")
        messages.error(request, "Veuillez corriger les erreurs du formulaire.")
    if not can_edit:
        for field in form.fields.values():
            field.disabled = True
    return render(request, "core/settings.html", {"form": form, "can_edit": can_edit, "page_title": "Paramètres"})


def error_403(request, exception=None):
    return render(request, "errors/403.html", {"page_title": "Accès refusé"}, status=403)


def error_404(request, exception=None):
    return render(request, "errors/404.html", {"page_title": "Page introuvable"}, status=404)

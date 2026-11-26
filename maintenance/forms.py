from django import forms
from django.utils import timezone

from core.forms import BootstrapFormMixin
from vehicles.models import Vehicle

from .models import Maintenance


class MaintenanceForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Maintenance
        fields = [
            "vehicle", "intervention_type", "status", "date", "mileage", "provider", "cost",
            "description", "next_date", "next_mileage", "invoice",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["vehicle"].queryset = Vehicle.objects.exclude(status=Vehicle.Status.OUT_OF_SERVICE) \
            if not self.instance.pk else Vehicle.objects.all()
        self.fields["next_date"].help_text = "Pour un entretien périodique (ex. vidange tous les 6 mois)."
        self.fields["next_mileage"].help_text = "Ex. kilométrage actuel + 5 000 km pour une vidange."

    def clean(self):
        data = super().clean()
        status, date = data.get("status"), data.get("date")
        if date and status in (Maintenance.Status.DONE, Maintenance.Status.IN_PROGRESS) and date > timezone.localdate():
            self.add_error("date", "Un entretien en cours ou terminé ne peut pas avoir une date future.")
        vehicle = data.get("vehicle")
        # Vérifié à la création ET à la modification (ex. un entretien planifié que l'on démarre)
        if status == Maintenance.Status.IN_PROGRESS and vehicle \
                and vehicle.assignments.filter(status="EN_COURS").exists():
            self.add_error("vehicle", "Ce véhicule est actuellement affecté : enregistrez son retour avant "
                                      "de le placer en entretien.")
        return data

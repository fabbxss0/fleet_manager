from django import forms
from django.utils import timezone

from core.forms import BootstrapFormMixin

from .models import Vehicle

# Statuts qu'un utilisateur peut choisir manuellement ; « Affecté » et
# « En entretien » sont gérés automatiquement par les affectations et entretiens.
MANUAL_STATUSES = (Vehicle.Status.AVAILABLE, Vehicle.Status.IMMOBILIZED, Vehicle.Status.OUT_OF_SERVICE)


class VehicleForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = [
            "registration_number", "brand", "model", "category", "fuel_type", "color", "year",
            "chassis_number", "acquisition_date", "acquisition_price", "mileage", "tank_capacity",
            "fiscal_power", "status", "photo", "notes",
        ]
        widgets = {"registration_number": forms.TextInput(attrs={"placeholder": "ex. 11 JK 4521"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        allowed = list(MANUAL_STATUSES)
        if self.instance.pk and self.instance.status not in allowed:
            allowed.insert(0, self.instance.status)
        self.fields["status"].choices = [c for c in Vehicle.Status.choices if c[0] in allowed]
        self.fields["status"].help_text = "« Affecté » et « En entretien » sont mis à jour automatiquement."

    def clean_registration_number(self):
        value = " ".join(self.cleaned_data["registration_number"].upper().split())
        if Vehicle.objects.filter(registration_number=value).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Un véhicule avec cette immatriculation existe déjà.")
        return value

    def clean_year(self):
        year = self.cleaned_data["year"]
        if year > timezone.localdate().year + 1:
            raise forms.ValidationError("L'année de fabrication ne peut pas être dans le futur.")
        return year

    def clean_acquisition_date(self):
        date = self.cleaned_data["acquisition_date"]
        if date > timezone.localdate():
            raise forms.ValidationError("La date d'acquisition ne peut pas être dans le futur.")
        return date

    def clean_mileage(self):
        mileage = self.cleaned_data["mileage"]
        if self.instance.pk and mileage < Vehicle.objects.get(pk=self.instance.pk).mileage:
            raise forms.ValidationError("Le kilométrage ne peut pas diminuer.")
        return mileage

    def clean(self):
        data = super().clean()
        year, acquisition = data.get("year"), data.get("acquisition_date")
        if year and acquisition and acquisition.year < year:
            self.add_error("acquisition_date", "Le véhicule ne peut pas être acquis avant sa fabrication.")
        status = data.get("status")
        if self.instance.pk and status == Vehicle.Status.AVAILABLE and self.instance.assignments.filter(status="EN_COURS").exists():
            self.add_error("status", "Ce véhicule a une affectation en cours : enregistrez d'abord son retour.")
        return data

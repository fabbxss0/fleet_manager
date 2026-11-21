from django import forms

from core.forms import BootstrapFormMixin

from .models import Driver


class DriverForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Driver
        fields = [
            "last_name", "first_name", "gender", "birth_date", "phone", "email", "address",
            "license_number", "license_category", "license_issue_date", "license_expiry_date",
            "hire_date", "status", "photo", "notes",
        ]

    def clean_license_number(self):
        return self.cleaned_data["license_number"].strip().upper()

    def clean(self):
        data = super().clean()
        if data.get("status") in (Driver.Status.INACTIVE, Driver.Status.SUSPENDED) and self.instance.pk \
                and self.instance.assignments.filter(status="EN_COURS").exists():
            self.add_error("status", "Ce conducteur a une affectation en cours : enregistrez d'abord le retour du véhicule.")
        if data.get("hire_date") and data.get("birth_date") and data["hire_date"] <= data["birth_date"]:
            self.add_error("hire_date", "La date d'embauche doit être postérieure à la date de naissance.")
        return data

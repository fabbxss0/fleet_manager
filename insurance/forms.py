from django import forms

from core.forms import BootstrapFormMixin

from .models import Insurance


class InsuranceForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Insurance
        fields = [
            "vehicle", "company", "policy_number", "insurance_type", "subscription_date",
            "start_date", "end_date", "premium", "document", "notes",
        ]

    def clean_policy_number(self):
        return self.cleaned_data["policy_number"].strip().upper()

    def clean(self):
        data = super().clean()
        vehicle, start, end = data.get("vehicle"), data.get("start_date"), data.get("end_date")
        if vehicle and start and end:
            # Deux polices ne doivent pas couvrir le même véhicule sur des périodes qui se chevauchent
            overlap = Insurance.objects.filter(vehicle=vehicle, start_date__lte=end, end_date__gte=start) \
                .exclude(pk=self.instance.pk).first()
            if overlap:
                self.add_error("start_date", f"Cette période chevauche la police {overlap.policy_number} "
                                             f"({overlap.start_date:%d/%m/%Y} – {overlap.end_date:%d/%m/%Y}).")
        return data

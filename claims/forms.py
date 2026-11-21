from django import forms

from core.forms import BootstrapFormMixin
from insurance.models import Insurance

from .models import Claim


class ClaimForm(BootstrapFormMixin, forms.ModelForm):
    immobilize = forms.BooleanField(
        label="Immobiliser le véhicule", required=False,
        help_text="Cochez si les dégâts empêchent le véhicule de rouler.",
    )

    class Meta:
        model = Claim
        fields = [
            "vehicle", "claim_type", "date", "location", "driver", "description", "third_party_involved",
            "injuries", "police_report_number", "estimated_cost", "repair_cost", "insurance", "insurance_status",
            "insurance_claim_number", "indemnity_amount", "status", "photo", "document",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["driver"].help_text = "Laissez vide : le conducteur de l'affectation en cours sera repris."
        self.fields["insurance"].help_text = "Laissez vide : la police valide à la date du sinistre sera reprise."
        self.fields["insurance"].queryset = Insurance.objects.select_related("vehicle")
        if self.instance.pk:
            self.fields["insurance"].queryset = Insurance.objects.filter(vehicle=self.instance.vehicle)
            del self.fields["immobilize"]

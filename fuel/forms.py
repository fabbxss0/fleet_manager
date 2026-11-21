from django import forms
from django.utils import timezone

from core.forms import BootstrapFormMixin
from drivers.models import Driver
from vehicles.models import Vehicle

from .models import FuelEntry


class FuelEntryForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = FuelEntry
        fields = ["vehicle", "driver", "date", "mileage", "liters", "unit_price", "full_tank", "station", "receipt", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "vehicle" in self.fields and not self.instance.pk:
            self.fields["vehicle"].queryset = Vehicle.objects.exclude(status=Vehicle.Status.OUT_OF_SERVICE)
        if not self.instance.pk:
            self.fields["date"].initial = timezone.localdate()
        if "driver" in self.fields:
            self.fields["driver"].queryset = Driver.objects.exclude(status=Driver.Status.INACTIVE)
        self.fields["liters"].widget.attrs["step"] = "0.01"
        self.fields["unit_price"].help_text = "Montant total calculé automatiquement : litres × prix du litre."


class DriverFuelEntryForm(FuelEntryForm):
    """Déclaration d'un plein par le conducteur : véhicule et conducteur sont imposés."""

    class Meta(FuelEntryForm.Meta):
        fields = ["date", "mileage", "liters", "unit_price", "full_tank", "station", "receipt", "notes"]

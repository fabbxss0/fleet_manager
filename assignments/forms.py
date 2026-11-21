from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from core.forms import BootstrapFormMixin
from drivers.models import Driver
from vehicles.models import Vehicle

from .models import Assignment
from .services import check_assignment_rules


class VehicleChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.registration_number} — {obj.brand} {obj.model} ({obj.mileage:,} km)".replace(",", " ")


class AssignmentCreateForm(BootstrapFormMixin, forms.ModelForm):
    vehicle = VehicleChoiceField(queryset=Vehicle.objects.none(), label="Véhicule")

    class Meta:
        model = Assignment
        fields = ["vehicle", "driver", "start_date", "expected_end_date", "start_mileage", "purpose", "destination", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Seuls les véhicules disponibles et les conducteurs libres sont proposés
        self.fields["vehicle"].queryset = Vehicle.objects.filter(status=Vehicle.Status.AVAILABLE)
        self.fields["driver"].queryset = Driver.objects.filter(
            status=Driver.Status.ACTIVE, license_expiry_date__gte=timezone.localdate()
        ).exclude(assignments__status=Assignment.Status.ACTIVE)
        self.fields["vehicle"].widget.attrs["data-mileage-source"] = "1"
        self.fields["start_date"].initial = timezone.localdate()
        # Kilométrage de chaque véhicule pour pré-remplir le champ en JavaScript (confort uniquement)
        self.vehicle_mileages = {v.pk: v.mileage for v in self.fields["vehicle"].queryset}

    def clean(self):
        data = super().clean()
        vehicle, driver = data.get("vehicle"), data.get("driver")
        if vehicle and driver:
            try:
                check_assignment_rules(vehicle, driver)
            except ValidationError as exc:
                for field, errors in exc.message_dict.items():
                    self.add_error(field if field in self.fields else None, errors)
        if vehicle and data.get("start_mileage") is not None and data["start_mileage"] < vehicle.mileage:
            self.add_error("start_mileage", f"Le kilométrage au départ ne peut pas être inférieur au compteur actuel "
                                            f"du véhicule ({vehicle.mileage} km).")
        if data.get("start_date") and data["start_date"] > timezone.localdate():
            self.add_error("start_date", "Une affectation en cours ne peut pas commencer dans le futur.")
        return data


class AssignmentUpdateForm(BootstrapFormMixin, forms.ModelForm):
    """Modification d'une affectation : le véhicule et le conducteur ne changent pas."""

    class Meta:
        model = Assignment
        fields = ["expected_end_date", "purpose", "destination", "notes"]


class AssignmentReturnForm(BootstrapFormMixin, forms.Form):
    return_date = forms.DateField(label="Date de retour effective")
    return_mileage = forms.IntegerField(label="Kilométrage au retour", min_value=0)
    notes = forms.CharField(label="Observations sur le retour", required=False, widget=forms.Textarea)

    def __init__(self, *args, assignment, **kwargs):
        self.assignment = assignment
        super().__init__(*args, **kwargs)
        self.fields["return_date"].initial = timezone.localdate()
        self.fields["return_mileage"].initial = assignment.vehicle.mileage

    def clean_return_mileage(self):
        mileage = self.cleaned_data["return_mileage"]
        if mileage < self.assignment.start_mileage:
            raise forms.ValidationError(
                f"Le kilométrage au retour ne peut pas être inférieur au kilométrage au départ "
                f"({self.assignment.start_mileage} km)."
            )
        return mileage

    def clean_return_date(self):
        date = self.cleaned_data["return_date"]
        if date < self.assignment.start_date:
            raise forms.ValidationError("La date de retour ne peut pas précéder la date de début.")
        if date > timezone.localdate():
            raise forms.ValidationError("La date de retour ne peut pas être dans le futur.")
        return date

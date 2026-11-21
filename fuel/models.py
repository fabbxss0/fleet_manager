"""Modèle Plein de carburant."""
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone

from core.validators import validate_document_file
from drivers.models import Driver
from vehicles.models import Vehicle


class FuelEntry(models.Model):
    vehicle = models.ForeignKey(Vehicle, verbose_name="véhicule", on_delete=models.PROTECT, related_name="fuel_entries")
    driver = models.ForeignKey(
        Driver, verbose_name="conducteur", on_delete=models.SET_NULL, null=True, blank=True, related_name="fuel_entries"
    )
    date = models.DateField("date du plein")
    mileage = models.PositiveIntegerField("kilométrage au compteur")
    liters = models.DecimalField("quantité (litres)", max_digits=7, decimal_places=2,
                                 validators=[MinValueValidator(Decimal("0.5"))])
    unit_price = models.DecimalField("prix du litre (FCFA)", max_digits=8, decimal_places=0,
                                     validators=[MinValueValidator(1)])
    total_amount = models.DecimalField("montant total (FCFA)", max_digits=12, decimal_places=0, editable=False)
    full_tank = models.BooleanField("plein complet", default=True,
                                    help_text="Cochez si le réservoir a été rempli entièrement (calcul de consommation).")
    station = models.CharField("station-service", max_length=120, blank=True)
    receipt = models.FileField("reçu", upload_to="fuel/", blank=True, null=True, validators=[validate_document_file])
    notes = models.CharField("observations", max_length=255, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   editable=False, related_name="+")
    created_at = models.DateTimeField("créé le", auto_now_add=True)

    class Meta:
        verbose_name = "plein de carburant"
        verbose_name_plural = "pleins de carburant"
        ordering = ["-date", "-mileage"]
        indexes = [models.Index(fields=["vehicle", "mileage"])]
        constraints = [
            models.CheckConstraint(condition=models.Q(liters__gt=0), name="fuel_liters_positive"),
        ]

    def __str__(self):
        return f"Plein {self.vehicle.registration_number} du {self.date:%d/%m/%Y} ({self.liters} L)"

    def get_absolute_url(self):
        return reverse("fuel:list") + f"?vehicle={self.vehicle_id}"

    def save(self, *args, **kwargs):
        # Le montant est toujours calculé côté serveur : litres × prix unitaire
        self.total_amount = (self.liters * self.unit_price).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        super().save(*args, **kwargs)

    def previous_entry(self):
        """Plein précédent du même véhicule (ordre du compteur)."""
        queryset = FuelEntry.objects.filter(vehicle_id=self.vehicle_id, mileage__lt=self.mileage)
        if self.pk:
            queryset = queryset.exclude(pk=self.pk)
        return queryset.order_by("-mileage").first()

    def clean(self):
        errors = {}
        if self.date and self.date > timezone.localdate():
            errors["date"] = "La date du plein ne peut pas être dans le futur."
        if self.vehicle_id and self.liters:
            tank = self.vehicle.tank_capacity
            if tank and self.liters > Decimal(tank) * Decimal("1.05"):
                errors["liters"] = f"Quantité supérieure à la capacité du réservoir ({tank} L)."
        if self.vehicle_id and self.mileage is not None and self.date:
            # Cohérence du compteur avec les pleins voisins dans le temps
            others = FuelEntry.objects.filter(vehicle_id=self.vehicle_id).exclude(pk=self.pk)
            before = others.filter(date__lte=self.date).order_by("-mileage").first()
            after = others.filter(date__gt=self.date).order_by("mileage").first()
            if before and self.mileage < before.mileage:
                errors["mileage"] = (f"Le compteur ne peut pas être inférieur à celui du plein du "
                                     f"{before.date:%d/%m/%Y} ({before.mileage} km).")
            elif after and self.mileage > after.mileage:
                errors["mileage"] = (f"Le compteur ne peut pas dépasser celui du plein suivant du "
                                     f"{after.date:%d/%m/%Y} ({after.mileage} km).")
        if errors:
            raise ValidationError(errors)

"""Modèle Entretien / Réparation."""
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse

from core.validators import validate_document_file
from vehicles.models import Vehicle


class Maintenance(models.Model):
    class InterventionType(models.TextChoices):
        OIL_CHANGE = "VIDANGE", "Vidange"
        SERVICE = "REVISION", "Révision générale"
        TIRES = "PNEUS", "Changement de pneus"
        MECHANICAL = "MECANIQUE", "Réparation mécanique"
        ELECTRICAL = "ELECTRIQUE", "Réparation électrique"
        BRAKES = "FREINAGE", "Freinage"
        BATTERY = "BATTERIE", "Batterie"
        BODYWORK = "CARROSSERIE", "Carrosserie"
        TECHNICAL_CONTROL = "CONTROLE_TECHNIQUE", "Contrôle technique"
        OTHER = "AUTRE", "Autres"

    class Status(models.TextChoices):
        PLANNED = "PLANIFIE", "Planifié"
        IN_PROGRESS = "EN_COURS", "En cours"
        DONE = "TERMINE", "Terminé"
        CANCELLED = "ANNULE", "Annulé"

    vehicle = models.ForeignKey(Vehicle, verbose_name="véhicule", on_delete=models.PROTECT, related_name="maintenances")
    intervention_type = models.CharField("type d'intervention", max_length=30, choices=InterventionType.choices)
    description = models.TextField("description")
    date = models.DateField("date de l'intervention")
    mileage = models.PositiveIntegerField("kilométrage lors de l'intervention")
    provider = models.CharField("garage / prestataire", max_length=120)
    cost = models.DecimalField("coût (FCFA)", max_digits=12, decimal_places=0, default=0, validators=[MinValueValidator(0)])
    next_date = models.DateField("date du prochain entretien", null=True, blank=True)
    next_mileage = models.PositiveIntegerField("kilométrage du prochain entretien", null=True, blank=True)
    status = models.CharField("statut", max_length=20, choices=Status.choices, default=Status.DONE)
    invoice = models.FileField(
        "facture / justificatif", upload_to="maintenance/", blank=True, null=True, validators=[validate_document_file]
    )
    created_at = models.DateTimeField("créé le", auto_now_add=True)
    updated_at = models.DateTimeField("modifié le", auto_now=True)

    class Meta:
        verbose_name = "entretien"
        verbose_name_plural = "entretiens"
        ordering = ["-date", "-id"]
        indexes = [models.Index(fields=["vehicle", "intervention_type", "date"])]

    def __str__(self):
        return f"{self.get_intervention_type_display()} — {self.vehicle.registration_number} ({self.date:%d/%m/%Y})"

    def get_absolute_url(self):
        return reverse("maintenance:detail", args=[self.pk])

    def clean(self):
        errors = {}
        if self.next_date and self.date and self.next_date <= self.date:
            errors["next_date"] = "La date du prochain entretien doit être postérieure à la date de l'intervention."
        if self.next_mileage is not None and self.mileage is not None and self.next_mileage <= self.mileage:
            errors["next_mileage"] = "Le kilométrage prévu doit être supérieur au kilométrage de l'intervention."
        if errors:
            raise ValidationError(errors)

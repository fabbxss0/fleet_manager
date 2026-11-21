"""Modèle Affectation : un véhicule confié à un conducteur pour une période."""
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from drivers.models import Driver
from vehicles.models import Vehicle


class Assignment(models.Model):
    class FuelLevel(models.IntegerChoices):
        EMPTY = 0, "Réserve"
        QUARTER = 25, "1/4"
        HALF = 50, "1/2"
        THREE_QUARTERS = 75, "3/4"
        FULL = 100, "Plein"

    class Condition(models.TextChoices):
        OK = "RAS", "RAS (bon état)"
        MINOR = "LEGER", "Dommages légers"
        MAJOR = "IMPORTANT", "Dommages importants"

    class Status(models.TextChoices):
        ACTIVE = "EN_COURS", "En cours"
        DONE = "TERMINEE", "Terminée"
        CANCELLED = "ANNULEE", "Annulée"

    # PROTECT : on ne peut pas supprimer un véhicule / conducteur qui possède un historique
    vehicle = models.ForeignKey(Vehicle, verbose_name="véhicule", on_delete=models.PROTECT, related_name="assignments")
    driver = models.ForeignKey(Driver, verbose_name="conducteur", on_delete=models.PROTECT, related_name="assignments")
    start_date = models.DateField("date de début")
    expected_end_date = models.DateField("date de fin prévue")
    actual_return_date = models.DateField("date de retour effective", null=True, blank=True)
    start_mileage = models.PositiveIntegerField("kilométrage au départ")
    return_mileage = models.PositiveIntegerField("kilométrage au retour", null=True, blank=True)
    purpose = models.CharField("motif de l'affectation", max_length=200)
    destination = models.CharField("destination", max_length=150, blank=True)
    start_fuel_level = models.PositiveSmallIntegerField("carburant au départ", choices=FuelLevel.choices,
                                                        null=True, blank=True)
    return_fuel_level = models.PositiveSmallIntegerField("carburant au retour", choices=FuelLevel.choices,
                                                         null=True, blank=True)
    return_condition = models.CharField("état au retour", max_length=20, choices=Condition.choices, blank=True)
    damage_notes = models.TextField("description des dommages", blank=True)
    notes = models.TextField("observations", blank=True)
    status = models.CharField("statut", max_length=20, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField("créée le", auto_now_add=True)
    updated_at = models.DateTimeField("modifiée le", auto_now=True)

    class Meta:
        verbose_name = "affectation"
        verbose_name_plural = "affectations"
        ordering = ["-start_date", "-id"]
        constraints = [
            # Règles de gestion garanties directement par la base de données
            models.UniqueConstraint(
                fields=["vehicle"], condition=Q(status="EN_COURS"), name="unique_active_assignment_per_vehicle",
                violation_error_message="Ce véhicule a déjà une affectation en cours.",
            ),
            models.UniqueConstraint(
                fields=["driver"], condition=Q(status="EN_COURS"), name="unique_active_assignment_per_driver",
                violation_error_message="Ce conducteur a déjà un véhicule affecté.",
            ),
            models.CheckConstraint(
                condition=Q(expected_end_date__gte=models.F("start_date")),
                name="assignment_end_after_start",
                violation_error_message="La date de fin prévue doit être postérieure à la date de début.",
            ),
            models.CheckConstraint(
                condition=Q(return_mileage__isnull=True) | Q(return_mileage__gte=models.F("start_mileage")),
                name="assignment_return_mileage_gte_start",
                violation_error_message="Le kilométrage au retour ne peut pas être inférieur au kilométrage au départ.",
            ),
        ]

    def __str__(self):
        return f"{self.vehicle.registration_number} → {self.driver.full_name} ({self.start_date:%d/%m/%Y})"

    def get_absolute_url(self):
        return reverse("assignments:detail", args=[self.pk])

    def clean(self):
        """Validations de cohérence des dates et kilométrages (côté serveur)."""
        errors = {}
        if self.start_date and self.expected_end_date and self.expected_end_date < self.start_date:
            errors["expected_end_date"] = "La date de fin prévue doit être postérieure ou égale à la date de début."
        if self.actual_return_date and self.start_date and self.actual_return_date < self.start_date:
            errors["actual_return_date"] = "La date de retour ne peut pas précéder la date de début."
        if self.actual_return_date and self.actual_return_date > timezone.localdate():
            errors["actual_return_date"] = "La date de retour ne peut pas être dans le futur."
        if self.return_mileage is not None and self.start_mileage is not None and self.return_mileage < self.start_mileage:
            errors["return_mileage"] = "Le kilométrage au retour ne peut pas être inférieur au kilométrage au départ."
        if errors:
            raise ValidationError(errors)

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE

    @property
    def is_overdue(self):
        return self.is_active and self.expected_end_date < timezone.localdate()

    @property
    def distance(self):
        if self.return_mileage is None:
            return None
        return self.return_mileage - self.start_mileage

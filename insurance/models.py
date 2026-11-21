"""Modèle Assurance automobile."""
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone

from core.validators import validate_document_file
from vehicles.models import Vehicle


class Insurance(models.Model):
    class InsuranceType(models.TextChoices):
        THIRD_PARTY = "RC", "Responsabilité civile"
        ALL_RISKS = "TOUS_RISQUES", "Assurance tous risques"
        INTERMEDIATE = "INTERMEDIAIRE", "Assurance intermédiaire"
        OTHER = "AUTRE", "Autres"

    vehicle = models.ForeignKey(Vehicle, verbose_name="véhicule", on_delete=models.PROTECT, related_name="insurances")
    company = models.CharField("compagnie d'assurance", max_length=120)
    policy_number = models.CharField(
        "numéro de police", max_length=60, unique=True,
        error_messages={"unique": "Ce numéro de police existe déjà."},
    )
    insurance_type = models.CharField("type d'assurance", max_length=20, choices=InsuranceType.choices)
    subscription_date = models.DateField("date de souscription")
    start_date = models.DateField("début de validité")
    end_date = models.DateField("date d'expiration")
    premium = models.DecimalField("montant de la prime (FCFA)", max_digits=12, decimal_places=0, validators=[MinValueValidator(0)])
    document = models.FileField(
        "document justificatif", upload_to="insurance/", blank=True, null=True, validators=[validate_document_file]
    )
    notes = models.TextField("observations", blank=True)
    created_at = models.DateTimeField("créée le", auto_now_add=True)
    updated_at = models.DateTimeField("modifiée le", auto_now=True)

    class Meta:
        verbose_name = "assurance"
        verbose_name_plural = "assurances"
        ordering = ["-end_date"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gt=models.F("start_date")), name="insurance_end_after_start",
                violation_error_message="La date d'expiration doit être postérieure au début de validité.",
            ),
        ]

    def __str__(self):
        return f"{self.company} — {self.policy_number}"

    def get_absolute_url(self):
        return reverse("insurance:detail", args=[self.pk])

    def clean(self):
        errors = {}
        if self.start_date and self.end_date and self.end_date <= self.start_date:
            errors["end_date"] = "La date d'expiration doit être postérieure au début de validité."
        if self.subscription_date and self.start_date and self.subscription_date > self.start_date:
            errors["subscription_date"] = "La souscription doit précéder ou égaler le début de validité."
        if errors:
            raise ValidationError(errors)

    @property
    def days_remaining(self):
        return (self.end_date - timezone.localdate()).days

    @property
    def is_expired(self):
        return self.days_remaining < 0

    @property
    def state(self):
        """'expired', 'expiring' (≤ 30 j), 'upcoming' (pas encore commencée) ou 'valid'."""
        from core.models import AppSettings

        if self.is_expired:
            return "expired"
        if self.start_date > timezone.localdate():
            return "upcoming"
        if self.days_remaining <= AppSettings.load().alert_days_warning:
            return "expiring"
        return "valid"

    @property
    def state_label(self):
        return {"expired": "Expirée", "expiring": "Expire bientôt", "upcoming": "À venir", "valid": "Valide"}[self.state]

"""Modèle Sinistre : accident, vol, vandalisme… et son suivi auprès de l'assurance."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone

from assignments.models import Assignment
from core.validators import validate_document_file, validate_image_file
from drivers.models import Driver
from insurance.models import Insurance
from vehicles.models import Vehicle


class Claim(models.Model):
    class ClaimType(models.TextChoices):
        ACCIDENT = "ACCIDENT", "Accident de la circulation"
        THEFT = "VOL", "Vol"
        VANDALISM = "VANDALISME", "Vandalisme"
        GLASS = "BRIS_GLACE", "Bris de glace"
        FIRE = "INCENDIE", "Incendie"
        BREAKDOWN = "PANNE", "Panne grave"
        OTHER = "AUTRE", "Autre"

    class Status(models.TextChoices):
        OPEN = "OUVERT", "Ouvert"
        REPAIR = "EN_REPARATION", "En réparation"
        CLOSED = "CLOTURE", "Clôturé"

    class InsuranceStatus(models.TextChoices):
        NOT_DECLARED = "NON_DECLARE", "Non déclaré à l'assurance"
        DECLARED = "DECLARE", "Déclaré"
        IN_PROGRESS = "EN_COURS", "En cours d'expertise"
        COMPENSATED = "INDEMNISE", "Indemnisé"
        REFUSED = "REFUSE", "Refusé"

    vehicle = models.ForeignKey(Vehicle, verbose_name="véhicule", on_delete=models.PROTECT, related_name="claims")
    driver = models.ForeignKey(Driver, verbose_name="conducteur", on_delete=models.SET_NULL, null=True, blank=True,
                               related_name="claims")
    assignment = models.ForeignKey(Assignment, verbose_name="affectation liée", on_delete=models.SET_NULL,
                                   null=True, blank=True, related_name="claims")
    claim_type = models.CharField("type de sinistre", max_length=20, choices=ClaimType.choices)
    date = models.DateField("date du sinistre")
    location = models.CharField("lieu", max_length=150)
    description = models.TextField("circonstances")
    third_party_involved = models.BooleanField("tiers impliqué", default=False)
    injuries = models.BooleanField("blessés", default=False)
    police_report_number = models.CharField("n° de constat / PV", max_length=60, blank=True)
    estimated_cost = models.DecimalField("coût estimé (FCFA)", max_digits=12, decimal_places=0, default=0,
                                         validators=[MinValueValidator(0)])
    repair_cost = models.DecimalField("coût réel des réparations (FCFA)", max_digits=12, decimal_places=0,
                                      null=True, blank=True, validators=[MinValueValidator(0)])
    insurance = models.ForeignKey(Insurance, verbose_name="police d'assurance", on_delete=models.SET_NULL,
                                  null=True, blank=True, related_name="claims")
    insurance_status = models.CharField("suivi assurance", max_length=20, choices=InsuranceStatus.choices,
                                        default=InsuranceStatus.NOT_DECLARED)
    insurance_claim_number = models.CharField("n° de dossier assureur", max_length=60, blank=True)
    indemnity_amount = models.DecimalField("indemnité reçue (FCFA)", max_digits=12, decimal_places=0, default=0,
                                           validators=[MinValueValidator(0)])
    status = models.CharField("statut", max_length=20, choices=Status.choices, default=Status.OPEN)
    photo = models.ImageField("photo des dégâts", upload_to="claims/", blank=True, null=True,
                              validators=[validate_image_file])
    document = models.FileField("constat / rapport", upload_to="claims/", blank=True, null=True,
                                validators=[validate_document_file])
    closed_at = models.DateField("date de clôture", null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   editable=False, related_name="+")
    created_at = models.DateTimeField("créé le", auto_now_add=True)
    updated_at = models.DateTimeField("modifié le", auto_now=True)

    class Meta:
        verbose_name = "sinistre"
        verbose_name_plural = "sinistres"
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.get_claim_type_display()} — {self.vehicle.registration_number} ({self.date:%d/%m/%Y})"

    def get_absolute_url(self):
        return reverse("claims:detail", args=[self.pk])

    def clean(self):
        errors = {}
        if self.date and self.date > timezone.localdate():
            errors["date"] = "La date du sinistre ne peut pas être dans le futur."
        if self.insurance_id and self.vehicle_id and self.insurance.vehicle_id != self.vehicle_id:
            errors["insurance"] = "Cette police n'assure pas le véhicule concerné."
        if self.indemnity_amount and self.insurance_status != self.InsuranceStatus.COMPENSATED:
            errors["indemnity_amount"] = "Une indemnité ne peut être saisie que pour un dossier « Indemnisé »."
        if self.status == self.Status.CLOSED and self.repair_cost is None and self.claim_type != self.ClaimType.THEFT:
            errors["repair_cost"] = "Indiquez le coût réel des réparations avant de clôturer le sinistre."
        if errors:
            raise ValidationError(errors)

    @property
    def final_cost(self):
        """Coût retenu : réel s'il est connu, sinon estimé."""
        return self.repair_cost if self.repair_cost is not None else self.estimated_cost

    @property
    def net_cost(self):
        """Coût restant à la charge de l'organisation après indemnisation."""
        return max(self.final_cost - self.indemnity_amount, 0)

    @property
    def days_open(self):
        end = self.closed_at or timezone.localdate()
        return (end - self.date).days

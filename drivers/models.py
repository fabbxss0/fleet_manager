"""Modèle Conducteur."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone

from core.validators import validate_image_file


class Driver(models.Model):
    class Gender(models.TextChoices):
        MALE = "M", "Masculin"
        FEMALE = "F", "Féminin"

    class LicenseCategory(models.TextChoices):
        A = "A", "A (moto)"
        B = "B", "B (véhicule léger)"
        C = "C", "C (poids lourd)"
        D = "D", "D (transport de personnes)"
        E = "E", "E (remorque)"
        BC = "BC", "B + C"
        BCD = "BCDE", "B, C, D et E"

    class Status(models.TextChoices):
        ACTIVE = "ACTIF", "Actif"
        LEAVE = "CONGE", "En congé"
        SUSPENDED = "SUSPENDU", "Suspendu"
        INACTIVE = "INACTIF", "Inactif"

    class BloodGroup(models.TextChoices):
        A_POS = "A+", "A+"
        A_NEG = "A-", "A-"
        B_POS = "B+", "B+"
        B_NEG = "B-", "B-"
        AB_POS = "AB+", "AB+"
        AB_NEG = "AB-", "AB-"
        O_POS = "O+", "O+"
        O_NEG = "O-", "O-"

    # Compte utilisateur (rôle Conducteur) permettant d'accéder à l'espace personnel
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, verbose_name="compte utilisateur", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="driver_profile",
    )
    last_name = models.CharField("nom", max_length=80)
    first_name = models.CharField("prénom", max_length=80)
    gender = models.CharField("sexe", max_length=1, choices=Gender.choices)
    birth_date = models.DateField("date de naissance")
    phone = models.CharField("téléphone", max_length=30)
    address = models.CharField("adresse", max_length=200, blank=True)
    email = models.EmailField("email", blank=True)
    license_number = models.CharField(
        "numéro de permis", max_length=40, unique=True,
        error_messages={"unique": "Ce numéro de permis est déjà enregistré."},
    )
    license_category = models.CharField("catégorie du permis", max_length=10, choices=LicenseCategory.choices)
    license_issue_date = models.DateField("date de délivrance du permis")
    license_expiry_date = models.DateField("date d'expiration du permis")
    hire_date = models.DateField("date d'embauche")
    status = models.CharField("statut", max_length=20, choices=Status.choices, default=Status.ACTIVE)
    photo = models.ImageField("photo", upload_to="drivers/", blank=True, null=True, validators=[validate_image_file])
    employee_number = models.CharField(
        "matricule", max_length=30, unique=True, null=True, blank=True,
        error_messages={"unique": "Ce matricule est déjà attribué à un autre conducteur."},
    )
    department = models.CharField("service / département", max_length=100, blank=True)
    blood_group = models.CharField("groupe sanguin", max_length=3, choices=BloodGroup.choices, blank=True)
    emergency_contact_name = models.CharField("personne à prévenir", max_length=120, blank=True)
    emergency_contact_phone = models.CharField("téléphone d'urgence", max_length=30, blank=True)
    notes = models.TextField("observations", blank=True)
    created_at = models.DateTimeField("créé le", auto_now_add=True)
    updated_at = models.DateTimeField("modifié le", auto_now=True)

    class Meta:
        verbose_name = "conducteur"
        verbose_name_plural = "conducteurs"
        ordering = ["last_name", "first_name"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(license_expiry_date__gt=models.F("license_issue_date")),
                name="driver_license_expiry_after_issue",
            ),
        ]

    def __str__(self):
        return self.full_name

    def get_absolute_url(self):
        return reverse("drivers:detail", args=[self.pk])

    def clean(self):
        errors = {}
        today = timezone.localdate()
        if self.birth_date and self.birth_date > today.replace(year=today.year - 18):
            errors["birth_date"] = "Le conducteur doit avoir au moins 18 ans."
        if self.license_issue_date and self.license_expiry_date and self.license_expiry_date <= self.license_issue_date:
            errors["license_expiry_date"] = "La date d'expiration doit être postérieure à la date de délivrance."
        if self.license_issue_date and self.license_issue_date > today:
            errors["license_issue_date"] = "La date de délivrance ne peut pas être dans le futur."
        if self.birth_date and self.license_issue_date and self.license_issue_date <= self.birth_date:
            errors["license_issue_date"] = "La date de délivrance doit être postérieure à la date de naissance."
        if errors:
            raise ValidationError(errors)

    @property
    def full_name(self):
        return f"{self.last_name.upper()} {self.first_name}"

    @property
    def initials(self):
        return (self.first_name[:1] + self.last_name[:1]).upper()

    @property
    def license_days_remaining(self):
        return (self.license_expiry_date - timezone.localdate()).days

    @property
    def license_is_expired(self):
        return self.license_days_remaining < 0

    @property
    def current_assignment(self):
        return self.assignments.filter(status="EN_COURS").select_related("vehicle").first()

    @property
    def is_assignable(self):
        return self.status == self.Status.ACTIVE and not self.license_is_expired

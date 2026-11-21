"""Modèle Véhicule."""
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Sum
from django.urls import reverse
from django.utils import timezone

from core.validators import validate_image_file


def current_year():
    return timezone.localdate().year


class Vehicle(models.Model):
    class Category(models.TextChoices):
        SEDAN = "BERLINE", "Berline"
        SUV = "SUV", "SUV"
        PICKUP = "PICKUP", "Pick-up"
        VAN = "CAMIONNETTE", "Camionnette"
        TRUCK = "CAMION", "Camion"
        MINIBUS = "MINIBUS", "Minibus"
        MOTO = "MOTO", "Moto"
        OTHER = "AUTRE", "Autres"

    class Fuel(models.TextChoices):
        GASOLINE = "ESSENCE", "Essence"
        DIESEL = "DIESEL", "Diesel"
        HYBRID = "HYBRIDE", "Hybride"
        ELECTRIC = "ELECTRIQUE", "Électrique"
        OTHER = "AUTRE", "Autre"

    class Status(models.TextChoices):
        AVAILABLE = "DISPONIBLE", "Disponible"
        ASSIGNED = "AFFECTE", "Affecté"
        MAINTENANCE = "EN_ENTRETIEN", "En entretien"
        IMMOBILIZED = "IMMOBILISE", "Immobilisé"
        OUT_OF_SERVICE = "HORS_SERVICE", "Hors service"

    class Transmission(models.TextChoices):
        MANUAL = "MANUELLE", "Manuelle"
        AUTOMATIC = "AUTOMATIQUE", "Automatique"

    # Statuts empêchant toute nouvelle affectation
    NON_ASSIGNABLE_STATUSES = (Status.MAINTENANCE, Status.IMMOBILIZED, Status.OUT_OF_SERVICE)

    registration_number = models.CharField(
        "immatriculation", max_length=20, unique=True,
        error_messages={"unique": "Un véhicule avec cette immatriculation existe déjà."},
    )
    brand = models.CharField("marque", max_length=60)
    model = models.CharField("modèle", max_length=60)
    category = models.CharField("catégorie", max_length=20, choices=Category.choices)
    fuel_type = models.CharField("carburant", max_length=20, choices=Fuel.choices)
    color = models.CharField("couleur", max_length=40, blank=True)
    year = models.PositiveIntegerField(
        "année de fabrication", validators=[MinValueValidator(1950), MaxValueValidator(2100)]
    )
    chassis_number = models.CharField(
        "numéro de châssis", max_length=40, unique=True,
        error_messages={"unique": "Ce numéro de châssis est déjà enregistré."},
    )
    acquisition_date = models.DateField("date d'acquisition")
    acquisition_price = models.DecimalField(
        "prix d'acquisition (FCFA)", max_digits=14, decimal_places=0, validators=[MinValueValidator(0)]
    )
    mileage = models.PositiveIntegerField("kilométrage actuel", default=0)
    tank_capacity = models.PositiveIntegerField("capacité du réservoir (L)", null=True, blank=True)
    fiscal_power = models.PositiveIntegerField("puissance fiscale (CV)", null=True, blank=True)
    photo = models.ImageField("photo", upload_to="vehicles/", blank=True, null=True, validators=[validate_image_file])
    status = models.CharField("statut", max_length=20, choices=Status.choices, default=Status.AVAILABLE)
    # --- Informations administratives
    registration_card_number = models.CharField("n° de carte grise", max_length=40, blank=True)
    first_registration_date = models.DateField("date de mise en circulation", null=True, blank=True)
    vignette_expiry_date = models.DateField(
        "échéance de la vignette / taxe annuelle", null=True, blank=True,
        help_text="Une alerte est générée à l'approche de cette date.",
    )
    department = models.CharField("service / département", max_length=100, blank=True)
    seats = models.PositiveSmallIntegerField("nombre de places", null=True, blank=True)
    transmission = models.CharField("boîte de vitesses", max_length=20, choices=Transmission.choices, blank=True)
    acquisition_mileage = models.PositiveIntegerField(
        "kilométrage à l'acquisition", default=0, help_text="Sert au calcul du coût de revient au kilomètre."
    )
    notes = models.TextField("observations", blank=True)
    created_at = models.DateTimeField("créé le", auto_now_add=True)
    updated_at = models.DateTimeField("modifié le", auto_now=True)

    class Meta:
        verbose_name = "véhicule"
        verbose_name_plural = "véhicules"
        ordering = ["registration_number"]

    def __str__(self):
        return f"{self.registration_number} — {self.brand} {self.model}"

    def save(self, *args, **kwargs):
        # Immatriculation et châssis normalisés en majuscules sans espaces superflus
        self.registration_number = self.registration_number.strip().upper()
        self.chassis_number = self.chassis_number.strip().upper()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("vehicles:detail", args=[self.pk])

    @property
    def is_assignable(self):
        """Disponible ET couvert par une assurance valide aujourd'hui."""
        return self.status == self.Status.AVAILABLE and self.current_insurance is not None

    @property
    def total_maintenance_cost(self):
        """Somme des coûts des entretiens réalisés (hors annulés)."""
        return self.maintenances.exclude(status="ANNULE").aggregate(total=Sum("cost"))["total"] or 0

    @property
    def current_assignment(self):
        return self.assignments.filter(status="EN_COURS").select_related("driver").first()

    @classmethod
    def insured_today_filter(cls):
        """Condition ORM : véhicule couvert par une assurance valide aujourd'hui."""
        today = timezone.localdate()
        return models.Q(insurances__start_date__lte=today, insurances__end_date__gte=today)

    @property
    def current_insurance(self):
        today = timezone.localdate()
        return self.insurances.filter(start_date__lte=today, end_date__gte=today).order_by("-end_date").first()

    def refresh_status(self, save=True):
        """
        Recalcule le statut « automatique » du véhicule après la fin d'une
        affectation ou d'un entretien. Les statuts Immobilisé et Hors service
        sont des décisions manuelles : on ne les modifie jamais ici.
        """
        if self.pk:
            self.refresh_from_db(fields=["status"])  # on part toujours de la valeur réelle en base
        if self.status in (self.Status.IMMOBILIZED, self.Status.OUT_OF_SERVICE):
            return self.status
        if self.maintenances.filter(status="EN_COURS").exists():
            new_status = self.Status.MAINTENANCE
        elif self.assignments.filter(status="EN_COURS").exists():
            new_status = self.Status.ASSIGNED
        else:
            new_status = self.Status.AVAILABLE
        if new_status != self.status:
            self.status = new_status
            if save:
                self.save(update_fields=["status", "updated_at"])
        return self.status

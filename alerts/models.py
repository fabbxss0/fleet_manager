"""Modèle Alerte : notification générée automatiquement à partir des échéances."""
from django.conf import settings
from django.db import models
from django.db.models import Exists, OuterRef, Q
from django.urls import reverse


class AlertQuerySet(models.QuerySet):
    """Le statut « lue » dépend de l'utilisateur : chacun gère ses propres alertes lues."""

    def with_read_state(self, user):
        """Ajoute l'attribut `is_read` (vrai si CET utilisateur a lu l'alerte)."""
        return self.annotate(is_read=Exists(AlertRead.objects.filter(alert=OuterRef("pk"), user=user)))

    def unread_for(self, user):
        return self.with_read_state(user).filter(is_read=False)

    def read_for(self, user):
        return self.with_read_state(user).filter(is_read=True)


class Alert(models.Model):
    class Category(models.TextChoices):
        INSURANCE = "ASSURANCE", "Assurance"
        LICENSE = "PERMIS", "Permis de conduire"
        MAINTENANCE = "ENTRETIEN", "Entretien"
        TECHNICAL_CONTROL = "CONTROLE_TECHNIQUE", "Contrôle technique"
        VEHICLE = "VEHICULE", "Véhicule"
        ASSIGNMENT = "AFFECTATION", "Affectation"
        FUEL = "CARBURANT", "Carburant"
        TAX = "VIGNETTE", "Vignette / taxe"
        CLAIM = "SINISTRE", "Sinistre"

    class Priority(models.IntegerChoices):
        # Valeurs numériques pour pouvoir trier du plus grave au moins grave
        INFO = 1, "Information"
        WARNING = 2, "Attention"
        URGENT = 3, "Urgent"
        CRITICAL = 4, "Critique"

    title = models.CharField("titre", max_length=200)
    description = models.TextField("description")
    category = models.CharField("catégorie", max_length=30, choices=Category.choices)
    priority = models.PositiveSmallIntegerField("priorité", choices=Priority.choices, default=Priority.INFO)
    read_by = models.ManyToManyField(settings.AUTH_USER_MODEL, through="AlertRead", related_name="read_alerts",
                                     blank=True, verbose_name="lue par")
    is_resolved = models.BooleanField(
        "résolue", default=False, help_text="La situation à l'origine de l'alerte n'existe plus."
    )
    created_at = models.DateTimeField("créée le", auto_now_add=True)
    resolved_at = models.DateTimeField("résolue le", null=True, blank=True)
    emailed_at = models.DateTimeField("notifiée par email le", null=True, blank=True)
    # Clé technique décrivant la situation (ex. « insurance:12:j7 ») : empêche les doublons
    dedup_key = models.CharField("clé de déduplication", max_length=120, db_index=True)
    # Élément concerné (une alerte peut concerner un véhicule, un conducteur ou une affectation)
    vehicle = models.ForeignKey("vehicles.Vehicle", on_delete=models.CASCADE, null=True, blank=True, related_name="alerts")
    driver = models.ForeignKey("drivers.Driver", on_delete=models.CASCADE, null=True, blank=True, related_name="alerts")
    assignment = models.ForeignKey(
        "assignments.Assignment", on_delete=models.CASCADE, null=True, blank=True, related_name="alerts"
    )
    insurance = models.ForeignKey("insurance.Insurance", on_delete=models.CASCADE, null=True, blank=True, related_name="alerts")
    maintenance = models.ForeignKey(
        "maintenance.Maintenance", on_delete=models.CASCADE, null=True, blank=True, related_name="alerts"
    )
    claim = models.ForeignKey("claims.Claim", on_delete=models.CASCADE, null=True, blank=True, related_name="alerts")
    fuel_entry = models.ForeignKey("fuel.FuelEntry", on_delete=models.CASCADE, null=True, blank=True, related_name="alerts")

    class Meta:
        verbose_name = "alerte"
        verbose_name_plural = "alertes"
        ordering = ["-priority", "-created_at"]
        constraints = [
            # Une seule alerte active (non résolue) par situation
            models.UniqueConstraint(fields=["dedup_key"], condition=Q(is_resolved=False), name="unique_open_alert"),
        ]

    objects = AlertQuerySet.as_manager()

    def __str__(self):
        return self.title

    def mark_read(self, user):
        AlertRead.objects.get_or_create(alert=self, user=user)

    def mark_unread(self, user):
        AlertRead.objects.filter(alert=self, user=user).delete()

    def is_read_by(self, user):
        return AlertRead.objects.filter(alert=self, user=user).exists()

    @property
    def target_url(self):
        """Lien vers l'élément concerné par l'alerte."""
        for obj in (self.claim, self.insurance, self.maintenance, self.fuel_entry, self.assignment, self.driver, self.vehicle):
            if obj is not None:
                return obj.get_absolute_url()
        return reverse("alerts:list")

    @property
    def priority_color(self):
        return {1: "info", 2: "warning", 3: "orange", 4: "danger"}[self.priority]

    @property
    def category_icon(self):
        return {
            "ASSURANCE": "shield-check", "PERMIS": "person-vcard", "ENTRETIEN": "tools",
            "CONTROLE_TECHNIQUE": "clipboard-check", "VEHICULE": "car-front", "AFFECTATION": "arrow-left-right", "CARBURANT": "fuel-pump", "VIGNETTE": "receipt", "SINISTRE": "exclamation-diamond",
        }.get(self.category, "bell")


class AlertRead(models.Model):
    """Table d'association : tel utilisateur a lu telle alerte, à telle date."""
    alert = models.ForeignKey(Alert, on_delete=models.CASCADE, related_name="reads")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="alert_reads")
    read_at = models.DateTimeField("lue le", auto_now_add=True)

    class Meta:
        verbose_name = "lecture d'alerte"
        verbose_name_plural = "lectures d'alertes"
        constraints = [models.UniqueConstraint(fields=["alert", "user"], name="unique_alert_read_per_user")]

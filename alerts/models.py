"""Modèle Alerte : notification générée automatiquement à partir des échéances."""
from django.db import models
from django.db.models import Q
from django.urls import reverse


class Alert(models.Model):
    class Category(models.TextChoices):
        INSURANCE = "ASSURANCE", "Assurance"
        LICENSE = "PERMIS", "Permis de conduire"
        MAINTENANCE = "ENTRETIEN", "Entretien"
        TECHNICAL_CONTROL = "CONTROLE_TECHNIQUE", "Contrôle technique"
        VEHICLE = "VEHICULE", "Véhicule"
        ASSIGNMENT = "AFFECTATION", "Affectation"

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
    is_read = models.BooleanField("lue", default=False)
    is_resolved = models.BooleanField(
        "résolue", default=False, help_text="La situation à l'origine de l'alerte n'existe plus."
    )
    created_at = models.DateTimeField("créée le", auto_now_add=True)
    resolved_at = models.DateTimeField("résolue le", null=True, blank=True)
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

    class Meta:
        verbose_name = "alerte"
        verbose_name_plural = "alertes"
        ordering = ["is_read", "-priority", "-created_at"]
        constraints = [
            # Une seule alerte active (non résolue) par situation
            models.UniqueConstraint(fields=["dedup_key"], condition=Q(is_resolved=False), name="unique_open_alert"),
        ]

    def __str__(self):
        return self.title

    @property
    def target_url(self):
        """Lien vers l'élément concerné par l'alerte."""
        for obj in (self.insurance, self.maintenance, self.assignment, self.driver, self.vehicle):
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
            "CONTROLE_TECHNIQUE": "clipboard-check", "VEHICULE": "car-front", "AFFECTATION": "arrow-left-right",
        }.get(self.category, "bell")

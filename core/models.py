"""Paramètres généraux de l'application (enregistrement unique)."""
from django.db import models


class AppSettings(models.Model):
    """
    Paramètres modifiables depuis la page « Paramètres ».
    Une seule ligne existe en base : on y accède avec AppSettings.load().
    """

    organization_name = models.CharField("nom de l'organisation", max_length=150, default="Mon organisation")
    alert_days_warning = models.PositiveIntegerField(
        "seuil d'alerte (jours)", default=30, help_text="Première alerte avant une échéance (assurance, permis)."
    )
    alert_days_urgent = models.PositiveIntegerField(
        "seuil urgent (jours)", default=7, help_text="Alerte urgente avant une échéance."
    )
    maintenance_days_threshold = models.PositiveIntegerField(
        "anticipation entretien (jours)", default=15,
        help_text="Un entretien est signalé « prochainement nécessaire » ce nombre de jours avant sa date.",
    )
    maintenance_km_threshold = models.PositiveIntegerField(
        "anticipation entretien (km)", default=1000,
        help_text="Un entretien est signalé lorsque le véhicule est à moins de ce nombre de km de l'échéance.",
    )
    technical_control_days = models.PositiveIntegerField(
        "anticipation contrôle technique (jours)", default=30
    )

    class Meta:
        verbose_name = "paramètres de l'application"
        verbose_name_plural = "paramètres de l'application"

    def save(self, *args, **kwargs):
        self.pk = 1  # garantit l'unicité de l'enregistrement
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return "Paramètres"

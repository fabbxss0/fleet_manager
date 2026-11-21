"""Journal d'audit : trace non modifiable des actions des utilisateurs."""
from django.apps import apps
from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    class Action(models.TextChoices):
        CREATE = "CREATION", "Création"
        UPDATE = "MODIFICATION", "Modification"
        DELETE = "SUPPRESSION", "Suppression"
        LOGIN = "CONNEXION", "Connexion"
        LOGOUT = "DECONNEXION", "Déconnexion"
        LOGIN_FAILED = "ECHEC_CONNEXION", "Échec de connexion"

    timestamp = models.DateTimeField("date et heure", auto_now_add=True, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="utilisateur", on_delete=models.SET_NULL,
                             null=True, blank=True, related_name="audit_logs")
    # Copie du nom : le journal reste lisible même si le compte est supprimé
    username = models.CharField("identifiant", max_length=150, blank=True)
    action = models.CharField("action", max_length=20, choices=Action.choices)
    model_label = models.CharField("modèle technique", max_length=100, blank=True, db_index=True)
    model_name = models.CharField("type d'élément", max_length=100, blank=True)
    object_id = models.CharField("identifiant de l'élément", max_length=50, blank=True)
    object_repr = models.CharField("élément", max_length=255, blank=True)
    # {"Libellé du champ": ["ancienne valeur", "nouvelle valeur"]}
    changes = models.JSONField("modifications", default=dict, blank=True)
    ip_address = models.GenericIPAddressField("adresse IP", null=True, blank=True)

    class Meta:
        verbose_name = "entrée du journal"
        verbose_name_plural = "journal d'audit"
        ordering = ["-timestamp", "-id"]
        indexes = [models.Index(fields=["model_label", "object_id"])]

    def __str__(self):
        return f"{self.timestamp:%d/%m/%Y %H:%M} — {self.username or 'Système'} — {self.get_action_display()} {self.object_repr}"

    def save(self, *args, **kwargs):
        # Une entrée de journal ne se modifie jamais : on ne fait que des ajouts
        if self.pk:
            raise ValueError("Une entrée du journal d'audit ne peut pas être modifiée.")
        super().save(*args, **kwargs)

    @property
    def target_url(self):
        """Lien vers l'élément s'il existe encore."""
        if not self.model_label or self.action == self.Action.DELETE:
            return None
        try:
            model = apps.get_model(self.model_label)
            obj = model.objects.filter(pk=self.object_id).first()
        except (LookupError, ValueError):
            return None
        return obj.get_absolute_url() if obj is not None and hasattr(obj, "get_absolute_url") else None

    @property
    def action_color(self):
        return {"CREATION": "success", "MODIFICATION": "primary", "SUPPRESSION": "danger",
                "CONNEXION": "secondary", "DECONNEXION": "secondary", "ECHEC_CONNEXION": "orange"}[self.action]

    @classmethod
    def for_object(cls, obj):
        return cls.objects.filter(model_label=obj._meta.label_lower, object_id=str(obj.pk)).select_related("user")

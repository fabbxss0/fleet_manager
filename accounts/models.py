"""Modèle utilisateur personnalisé avec gestion des rôles."""
from django.contrib.auth.models import AbstractUser
from django.db import models

from core.validators import validate_image_file


class User(AbstractUser):
    """Utilisateur de l'application. Le champ `role` détermine les droits d'accès."""

    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Administrateur"
        MANAGER = "GESTIONNAIRE", "Gestionnaire"
        DRIVER = "CONDUCTEUR", "Conducteur"

    role = models.CharField("rôle", max_length=20, choices=Role.choices, default=Role.MANAGER)
    phone = models.CharField("téléphone", max_length=30, blank=True)
    photo = models.ImageField(
        "photo", upload_to="users/", blank=True, null=True, validators=[validate_image_file]
    )

    class Meta:
        verbose_name = "utilisateur"
        verbose_name_plural = "utilisateurs"
        ordering = ["last_name", "first_name", "username"]

    def save(self, *args, **kwargs):
        # Un superutilisateur Django est toujours administrateur de l'application
        if self.is_superuser:
            self.role = self.Role.ADMIN
        super().save(*args, **kwargs)

    # --- Raccourcis utilisés dans les vues et les templates -----------------
    @property
    def is_admin(self):
        return self.role == self.Role.ADMIN

    @property
    def is_manager(self):
        return self.role == self.Role.MANAGER

    @property
    def is_driver(self):
        return self.role == self.Role.DRIVER

    @property
    def is_staff_member(self):
        """Administrateur ou gestionnaire : accès aux modules de gestion."""
        return self.role in (self.Role.ADMIN, self.Role.MANAGER)

    @property
    def initials(self):
        letters = (self.first_name[:1] + self.last_name[:1]) or self.username[:2]
        return letters.upper()

    @property
    def display_name(self):
        return self.get_full_name() or self.username

    def __str__(self):
        return self.display_name

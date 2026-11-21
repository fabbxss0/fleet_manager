"""Formulaires de connexion, de profil et de gestion des utilisateurs."""
from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, UserCreationForm

from core.forms import BootstrapFormMixin
from drivers.models import Driver

from .models import User


class LoginForm(BootstrapFormMixin, AuthenticationForm):
    error_messages = {
        "invalid_login": "Identifiant ou mot de passe incorrect. Vérifiez vos informations et réessayez.",
        "inactive": "Ce compte est désactivé. Contactez l'administrateur.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Nom d'utilisateur"
        self.fields["username"].widget.attrs.update({"placeholder": "ex. admin", "autofocus": True})
        self.fields["password"].label = "Mot de passe"


class ProfileForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "phone", "photo", "email_alerts"]
        labels = {"first_name": "Prénom", "last_name": "Nom", "email": "Adresse email"}


class StyledPasswordChangeForm(BootstrapFormMixin, PasswordChangeForm):
    pass


def _driver_queryset(instance=None):
    """Conducteurs pas encore rattachés à un compte (+ celui du compte édité)."""
    queryset = Driver.objects.filter(user__isnull=True)
    if instance is not None and hasattr(instance, "driver_profile"):
        queryset = queryset | Driver.objects.filter(pk=instance.driver_profile.pk)
    return queryset.order_by("last_name")


class DriverLinkMixin:
    """Champ « fiche conducteur » obligatoire pour les comptes de rôle Conducteur."""

    def _setup_driver_field(self, instance=None):
        self.fields["driver"] = forms.ModelChoiceField(
            queryset=_driver_queryset(instance), required=False, label="Fiche conducteur associée",
            help_text="Obligatoire pour un compte « Conducteur » : il ne verra que ses propres données.",
            widget=forms.Select(attrs={"class": "form-select"}),
        )
        if instance is not None and hasattr(instance, "driver_profile"):
            self.fields["driver"].initial = instance.driver_profile

    def clean(self):
        data = super().clean()
        if data.get("role") == User.Role.DRIVER and not data.get("driver"):
            self.add_error("driver", "Sélectionnez la fiche conducteur correspondant à ce compte.")
        return data

    def save_driver_link(self, user):
        driver = self.cleaned_data.get("driver")
        Driver.objects.filter(user=user).exclude(pk=getattr(driver, "pk", None)).update(user=None)
        if driver and user.role == User.Role.DRIVER:
            driver.user = user
            driver.save(update_fields=["user"])
        elif user.role != User.Role.DRIVER:
            Driver.objects.filter(user=user).update(user=None)


class UserCreateForm(BootstrapFormMixin, DriverLinkMixin, UserCreationForm):
    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "phone", "role"]
        labels = {"first_name": "Prénom", "last_name": "Nom", "email": "Adresse email"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._setup_driver_field()

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            self.save_driver_link(user)
        return user


class UserUpdateForm(BootstrapFormMixin, DriverLinkMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "phone", "role", "is_active"]
        labels = {"first_name": "Prénom", "last_name": "Nom", "email": "Adresse email", "is_active": "Compte actif"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._setup_driver_field(self.instance)

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            self.save_driver_link(user)
        return user

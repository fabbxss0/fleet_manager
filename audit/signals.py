"""
Enregistrement automatique des actions dans le journal d'audit.

- pre_save  : on photographie l'élément tel qu'il est en base AVANT modification ;
- post_save : on compare avec la nouvelle version et on note les champs changés ;
- post_delete : on garde une copie des dernières valeurs ;
- connexion, déconnexion et échec de connexion sont aussi tracés.

Remarque : QuerySet.update() ne déclenche pas les signaux Django ; le code de
l'application passe donc par save() pour toutes les modifications métier.
"""
from datetime import date, datetime
from decimal import Decimal

from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.db.models.signals import post_delete, post_save, pre_save

from .context import get_current_ip, get_current_user, is_disabled
from .models import AuditLog

# Champs jamais journalisés (techniques ou sensibles)
EXCLUDED_FIELDS = {"id", "created_at", "updated_at", "password", "last_login", "date_joined"}


def tracked_models():
    from accounts.models import User
    from assignments.models import Assignment
    from core.models import AppSettings
    from drivers.models import Driver
    from fuel.models import FuelEntry
    from insurance.models import Insurance
    from maintenance.models import Maintenance
    from vehicles.models import Vehicle

    return [Vehicle, Driver, Assignment, Maintenance, Insurance, FuelEntry, User, AppSettings]


def display_value(instance, field):
    """Valeur lisible d'un champ, comme l'utilisateur la voit à l'écran."""
    if field.is_relation:
        related = getattr(instance, field.name, None)
        return str(related) if related is not None else "—"
    value = getattr(instance, field.attname)
    if value in (None, ""):
        return "—"
    if field.choices:
        return str(dict(field.flatchoices).get(value, value))
    if isinstance(value, bool):
        return "Oui" if value else "Non"
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y %H:%M")
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, Decimal):
        return f"{value.normalize():f}"
    if hasattr(value, "name"):  # fichier téléversé
        return value.name or "—"
    return str(value)


def snapshot(instance):
    return {
        str(field.verbose_name).capitalize(): display_value(instance, field)
        for field in instance._meta.concrete_fields
        if field.name not in EXCLUDED_FIELDS and field.attname not in EXCLUDED_FIELDS
    }


def write_log(action, instance=None, changes=None, user=None, label=""):
    user = user or get_current_user()
    data = dict(action=action, user=user, username=user.get_username() if user else "",
                changes=changes or {}, ip_address=get_current_ip())
    if instance is not None:
        data.update(model_label=instance._meta.label_lower, model_name=str(instance._meta.verbose_name).capitalize(),
                    object_id=str(instance.pk), object_repr=str(instance)[:255])
    else:
        data["object_repr"] = label[:255]
    AuditLog.objects.create(**data)


def before_save(sender, instance, **kwargs):
    if is_disabled() or not instance.pk:
        instance._audit_before = None
        return
    old = sender.objects.filter(pk=instance.pk).first()
    instance._audit_before = snapshot(old) if old else None


def after_save(sender, instance, created, **kwargs):
    if is_disabled():
        return
    after = snapshot(instance)
    before = getattr(instance, "_audit_before", None)
    if created or before is None:
        changes = {k: ["—", v] for k, v in after.items() if v != "—"}
        write_log(AuditLog.Action.CREATE, instance, changes)
        return
    changes = {k: [before.get(k, "—"), v] for k, v in after.items() if before.get(k, "—") != v}
    if changes:  # une sauvegarde sans changement réel n'est pas journalisée
        write_log(AuditLog.Action.UPDATE, instance, changes)


def after_delete(sender, instance, **kwargs):
    if is_disabled():
        return
    changes = {k: [v, "—"] for k, v in snapshot(instance).items() if v != "—"}
    write_log(AuditLog.Action.DELETE, instance, changes)


def on_login(sender, request, user, **kwargs):
    write_log(AuditLog.Action.LOGIN, user=user, label=f"Connexion de {user.get_username()}")


def on_logout(sender, request, user, **kwargs):
    if user is not None:
        write_log(AuditLog.Action.LOGOUT, user=user, label=f"Déconnexion de {user.get_username()}")


def on_login_failed(sender, credentials, request=None, **kwargs):
    username = credentials.get("username", "?")
    log = AuditLog(action=AuditLog.Action.LOGIN_FAILED, username=username,
                   object_repr=f"Tentative de connexion échouée ({username})", ip_address=get_current_ip())
    log.save()


def connect():
    for model in tracked_models():
        uid = f"audit_{model._meta.label_lower}"
        pre_save.connect(before_save, sender=model, dispatch_uid=f"{uid}_pre")
        post_save.connect(after_save, sender=model, dispatch_uid=f"{uid}_post")
        post_delete.connect(after_delete, sender=model, dispatch_uid=f"{uid}_del")
    user_logged_in.connect(on_login, dispatch_uid="audit_login")
    user_logged_out.connect(on_logout, dispatch_uid="audit_logout")
    user_login_failed.connect(on_login_failed, dispatch_uid="audit_login_failed")

"""
Notification des alertes par email.

Un seul email récapitulatif est envoyé à chaque administrateur ou gestionnaire
actif qui a une adresse email et qui a accepté les notifications. Il liste
les NOUVELLES alertes urgentes et critiques (jamais envoyées). Chaque alerte
envoyée est datée (emailed_at) : elle ne sera pas renvoyée.
"""
from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.template.loader import render_to_string
from django.utils import timezone

from accounts.models import User

from .models import Alert


def recipients():
    return list(User.objects.filter(
        is_active=True, role__in=[User.Role.ADMIN, User.Role.MANAGER], email_alerts=True,
    ).exclude(email=""))


def pending_alerts():
    return Alert.objects.filter(is_resolved=False, emailed_at__isnull=True,
                                priority__gte=Alert.Priority.URGENT).order_by("-priority", "-created_at")


def send_alert_emails():
    """Envoie le récapitulatif. Retourne {"alerts": n, "recipients": n}."""
    alerts = list(pending_alerts())
    users = recipients()
    if not alerts or not users:
        return {"alerts": 0, "recipients": 0}
    context = {"alerts": alerts, "site_url": settings.SITE_URL.rstrip("/"), "date": timezone.localtime()}
    subject = f"[FLEET MANAGER] {len(alerts)} nouvelle(s) alerte(s) urgente(s)"
    text = render_to_string("alerts/email_digest.txt", context)
    html = render_to_string("alerts/email_digest.html", context)
    connection = get_connection()
    messages = []
    for user in users:  # un email par destinataire : les adresses ne sont pas visibles entre eux
        message = EmailMultiAlternatives(subject, text, settings.DEFAULT_FROM_EMAIL, [user.email], connection=connection)
        message.attach_alternative(html, "text/html")
        messages.append(message)
    connection.send_messages(messages)
    Alert.objects.filter(pk__in=[a.pk for a in alerts]).update(emailed_at=timezone.now())
    return {"alerts": len(alerts), "recipients": len(users)}


def send_test_email(user):
    message = EmailMultiAlternatives(
        "[FLEET MANAGER] Email de test",
        f"Bonjour {user.display_name},\n\nLa configuration des emails de FLEET MANAGER fonctionne.\n",
        settings.DEFAULT_FROM_EMAIL, [user.email],
    )
    message.send()

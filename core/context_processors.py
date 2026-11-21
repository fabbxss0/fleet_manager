"""Variables disponibles dans tous les templates (compteur d'alertes, paramètres)."""
from alerts.models import Alert

from .models import AppSettings


def app_context(request):
    context = {"APP_NAME": "FLEET MANAGER"}
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        context["app_settings"] = AppSettings.load()
        if user.is_staff_member:
            unread = Alert.objects.filter(is_resolved=False, is_read=False)
            context["unread_alerts_count"] = unread.count()
            context["latest_unread_alerts"] = unread.order_by("-priority", "-created_at")[:5]
    return context

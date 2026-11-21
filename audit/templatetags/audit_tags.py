from django import template

from audit.models import AuditLog

register = template.Library()


@register.inclusion_tag("audit/_history.html")
def audit_history(obj, limit=15):
    """Affiche l'historique des modifications d'un élément : {% audit_history object %}."""
    return {"entries": AuditLog.for_object(obj)[:limit]}

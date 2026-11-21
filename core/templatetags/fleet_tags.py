"""Filtres de template : montants FCFA, kilométrages, badges de statut, pagination."""
from decimal import Decimal, InvalidOperation

from django import template
from django.utils.html import format_html

register = template.Library()


def _group(number):
    """1234567 -> '1 234 567' (espace insécable fine comme séparateur des milliers)."""
    return f"{int(number):,}".replace(",", " ")


@register.filter
def fcfa(value):
    try:
        amount = Decimal(value or 0)
    except (InvalidOperation, TypeError, ValueError):
        return value
    return f"{_group(amount)} FCFA"


@register.filter
def km(value):
    if value in (None, ""):
        return "—"
    return f"{_group(value)} km"


@register.filter
def thousands(value):
    if value in (None, ""):
        return "—"
    return _group(value)


STATUS_COLORS = {
    # Véhicules
    "DISPONIBLE": "success", "AFFECTE": "primary", "EN_ENTRETIEN": "warning",
    "IMMOBILISE": "orange", "HORS_SERVICE": "secondary",
    # Conducteurs
    "ACTIF": "success", "CONGE": "info", "SUSPENDU": "orange", "INACTIF": "secondary",
    # Affectations
    "EN_COURS": "primary", "TERMINEE": "success", "ANNULEE": "secondary",
    # Entretiens
    "PLANIFIE": "info", "TERMINE": "success", "ANNULE": "secondary",
    # Assurances (état calculé)
    "valid": "success", "expiring": "warning", "expired": "danger", "upcoming": "info",
}


@register.simple_tag
def status_badge(value, label):
    color = STATUS_COLORS.get(value, "secondary")
    return format_html('<span class="badge badge-soft-{}">{}</span>', color, label)


@register.simple_tag(takes_context=True)
def query_transform(context, **kwargs):
    """Conserve les paramètres GET (filtres) en changeant de page."""
    query = context["request"].GET.copy()
    for key, value in kwargs.items():
        query[key] = value
    return query.urlencode()


@register.filter
def get_item(mapping, key):
    """Accès à une clé de dictionnaire dans un template : {{ dict|get_item:cle }}."""
    return mapping.get(key) if hasattr(mapping, "get") else None


@register.filter
def absolute(value):
    try:
        return abs(value)
    except TypeError:
        return value

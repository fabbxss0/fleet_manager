"""
Lecture sûre des paramètres d'URL (filtres, périodes, identifiants).

Un paramètre invalide tapé à la main dans l'adresse (?vehicle=abc, ?du=hier)
ne doit jamais provoquer d'erreur serveur : il est simplement ignoré.
"""
from datetime import date

from django.core.exceptions import ValidationError


def parse_int(value):
    """'12' -> 12 ; tout le reste -> None."""
    value = str(value or "").strip()
    return int(value) if value.isdigit() else None


def parse_date(value):
    """'2026-11-21' (format des champs date HTML) -> date ; valeur invalide -> None."""
    try:
        return date.fromisoformat(str(value).strip()) if value else None
    except ValueError:
        return None


def safe_filter(queryset, **lookups):
    """queryset.filter(...) qui ignore le filtre si sa valeur est invalide pour le champ."""
    try:
        return queryset.filter(**lookups)
    except (ValueError, TypeError, ValidationError):
        return queryset


def filter_period(queryset, params, field="date"):
    """Applique ?du= et ?au= sur `field` ; les dates invalides sont ignorées."""
    start, end = parse_date(params.get("du")), parse_date(params.get("au"))
    if start:
        queryset = queryset.filter(**{f"{field}__gte": start})
    if end:
        queryset = queryset.filter(**{f"{field}__lte": end})
    return queryset

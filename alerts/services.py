"""
Moteur de génération automatique des alertes.

Principe :
1. Chaque règle parcourt les données et produit des « alertes candidates »,
   identifiées par une clé unique décrivant la situation (dedup_key).
2. Si une alerte ouverte avec la même clé existe déjà, rien n'est créé :
   il n'y a donc jamais de doublon, même si la commande est lancée souvent.
3. Les alertes ouvertes dont la situation a disparu (assurance renouvelée,
   véhicule réparé…) sont automatiquement marquées comme « résolues ».

Point d'entrée : generate_alerts(). Elle est appelée par la commande
`python manage.py generate_alerts` et par le middleware de rafraîchissement.
"""
from dataclasses import dataclass, field

from django.db import transaction
from django.utils import timezone

from assignments.models import Assignment
from core.models import AppSettings
from drivers.models import Driver
from insurance.models import Insurance
from maintenance.services import get_due_schedules
from vehicles.models import Vehicle

from .models import Alert

P = Alert.Priority
C = Alert.Category


@dataclass
class Candidate:
    key: str
    title: str
    description: str
    category: str
    priority: int
    links: dict = field(default_factory=dict)


def _fmt(date):
    return date.strftime("%d/%m/%Y")


def _deadline_level(days_left, cfg):
    """Retourne (suffixe de clé, priorité) pour une échéance, ou None si rien à signaler."""
    if days_left < 0:
        return "expire", P.CRITICAL
    if days_left <= cfg.alert_days_urgent:
        return f"j{cfg.alert_days_urgent}", P.URGENT
    if days_left <= cfg.alert_days_warning:
        return f"j{cfg.alert_days_warning}", P.WARNING
    return None


def insurance_candidates(cfg):
    """Assurance expirant dans 30 j, dans 7 j, ou déjà expirée (dernière police de chaque véhicule)."""
    latest_by_vehicle = {}
    for insurance in Insurance.objects.select_related("vehicle").exclude(
        vehicle__status=Vehicle.Status.OUT_OF_SERVICE
    ).order_by("end_date"):
        latest_by_vehicle[insurance.vehicle_id] = insurance  # la plus tardive l'emporte
    for insurance in latest_by_vehicle.values():
        level = _deadline_level(insurance.days_remaining, cfg)
        if not level:
            continue
        suffix, priority = level
        reg = insurance.vehicle.registration_number
        if suffix == "expire":
            title = f"Assurance expirée — {reg}"
            desc = (f"La police {insurance.policy_number} ({insurance.company}) a expiré le {_fmt(insurance.end_date)}. "
                    "Le véhicule ne doit pas circuler sans couverture.")
        else:
            title = f"Assurance expirant le {_fmt(insurance.end_date)} — {reg}"
            desc = (f"La police {insurance.policy_number} ({insurance.company}) expire le {_fmt(insurance.end_date)}. "
                    "Pensez à la renouveler.")
        yield Candidate(f"insurance:{insurance.pk}:{suffix}", title, desc, C.INSURANCE, priority,
                        {"insurance": insurance, "vehicle": insurance.vehicle})


def license_candidates(cfg):
    """Permis expirant dans 30 j, dans 7 j, ou expiré (conducteurs non inactifs)."""
    for driver in Driver.objects.exclude(status=Driver.Status.INACTIVE):
        level = _deadline_level(driver.license_days_remaining, cfg)
        if not level:
            continue
        suffix, priority = level
        if suffix == "expire":
            title = f"Permis expiré — {driver.full_name}"
            desc = (f"Le permis n° {driver.license_number} a expiré le {_fmt(driver.license_expiry_date)}. "
                    "Le conducteur ne peut plus recevoir de véhicule.")
        else:
            title = f"Permis expirant le {_fmt(driver.license_expiry_date)} — {driver.full_name}"
            desc = f"Le permis n° {driver.license_number} expire le {_fmt(driver.license_expiry_date)}."
        yield Candidate(f"license:{driver.pk}:{suffix}", title, desc, C.LICENSE, priority, {"driver": driver})


def maintenance_candidates(cfg):
    """Entretiens bientôt nécessaires / dépassés et contrôles techniques à renouveler."""
    for item in get_due_schedules():
        m, vehicle = item["maintenance"], item["vehicle"]
        reg = vehicle.registration_number
        details = []
        if m.next_date:
            details.append(f"date prévue : {_fmt(m.next_date)}")
        if m.next_mileage:
            details.append(f"kilométrage prévu : {m.next_mileage:,} km (actuel : {vehicle.mileage:,} km)".replace(",", " "))
        detail_txt = " ; ".join(details)
        if item["is_technical_control"]:
            category = C.TECHNICAL_CONTROL
            if item["state"] == "overdue":
                title, priority = f"Contrôle technique dépassé — {reg}", P.CRITICAL
            else:
                title, priority = f"Contrôle technique à renouveler — {reg}", P.WARNING
        else:
            category = C.MAINTENANCE
            label = m.get_intervention_type_display().lower()
            if item["state"] == "overdue":
                title, priority = f"Entretien dépassé ({label}) — {reg}", P.URGENT
            else:
                title, priority = f"Entretien prochainement nécessaire ({label}) — {reg}", P.INFO
        yield Candidate(f"maintenance:{m.pk}:{item['state']}", title, f"Échéance : {detail_txt}.", category, priority,
                        {"maintenance": m, "vehicle": vehicle})


def vehicle_candidates(cfg):
    """Véhicules immobilisés."""
    for vehicle in Vehicle.objects.filter(status=Vehicle.Status.IMMOBILIZED):
        yield Candidate(
            f"vehicle:{vehicle.pk}:immobilise", f"Véhicule immobilisé — {vehicle.registration_number}",
            f"Le véhicule {vehicle.brand} {vehicle.model} est immobilisé et indisponible pour les missions.",
            C.VEHICLE, P.WARNING, {"vehicle": vehicle},
        )


def assignment_candidates(cfg):
    """Affectations en cours dont la date de retour prévue est dépassée."""
    today = timezone.localdate()
    overdue = Assignment.objects.filter(status=Assignment.Status.ACTIVE, expected_end_date__lt=today)
    for a in overdue.select_related("vehicle", "driver"):
        late = (today - a.expected_end_date).days
        yield Candidate(
            f"assignment:{a.pk}:retard", f"Retour en retard — {a.vehicle.registration_number}",
            f"{a.driver.full_name} devait restituer le véhicule le {_fmt(a.expected_end_date)} "
            f"({late} jour(s) de retard).",
            C.ASSIGNMENT, P.URGENT if late > 3 else P.WARNING,
            {"assignment": a, "vehicle": a.vehicle, "driver": a.driver},
        )


def fuel_candidates(cfg):
    """Consommation anormale : dernier plein > +30 % de la moyenne du véhicule."""
    from fuel.services import detect_anomalies

    for item in detect_anomalies():
        entry, vehicle = item["entry"], item["vehicle"]
        yield Candidate(
            f"fuel:{entry.pk}:anomalie", f"Consommation anormale — {vehicle.registration_number}",
            f"{item['consumption']} L/100 km au plein du {_fmt(entry.date)} contre {item['reference']} L/100 km "
            "habituellement. Vérifier une fuite, une panne ou un usage anormal.",
            C.FUEL, P.WARNING, {"fuel_entry": entry, "vehicle": vehicle},
        )


RULES = [insurance_candidates, license_candidates, maintenance_candidates, vehicle_candidates,
         assignment_candidates, fuel_candidates]


@transaction.atomic
def generate_alerts():
    """Exécute toutes les règles. Retourne un dict {created, resolved, open}."""
    cfg = AppSettings.load()
    open_alerts = {a.dedup_key: a for a in Alert.objects.filter(is_resolved=False)}
    seen_keys, created = set(), 0

    for rule in RULES:
        for candidate in rule(cfg):
            seen_keys.add(candidate.key)
            if candidate.key in open_alerts:
                continue  # déjà signalée : pas de doublon
            Alert.objects.create(
                dedup_key=candidate.key, title=candidate.title, description=candidate.description,
                category=candidate.category, priority=candidate.priority, **candidate.links,
            )
            created += 1

    # Résolution automatique des situations disparues
    to_resolve = [alert.pk for key, alert in open_alerts.items() if key not in seen_keys]
    resolved = Alert.objects.filter(pk__in=to_resolve).update(is_resolved=True, resolved_at=timezone.now())
    return {"created": created, "resolved": resolved, "open": Alert.objects.filter(is_resolved=False).count()}

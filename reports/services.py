"""
Définition des rapports.

Chaque rapport est une fonction qui reçoit la période (date_from, date_to) et
retourne une liste de « sections ». Une section contient un titre, des
colonnes, des lignes et éventuellement une ligne de total. Le même résultat
est ensuite affiché en HTML, exporté en PDF (ReportLab) ou en Excel (OpenPyXL) :
aucun code n'est dupliqué entre les trois formats.
"""
from dataclasses import dataclass, field

from django.db.models import Count, Sum
from django.utils import timezone

from alerts.models import Alert
from assignments.models import Assignment
from drivers.models import Driver
from claims import services as claim_services
from claims.models import Claim
from fuel import services as fuel_services
from fuel.models import FuelEntry
from insurance.models import Insurance
from maintenance import services as maintenance_services
from maintenance.models import Maintenance
from vehicles.models import Vehicle


@dataclass
class Section:
    title: str
    columns: list
    rows: list = field(default_factory=list)
    total: list | None = None
    # Index des colonnes contenant des montants FCFA / nombres (alignés à droite)
    money_columns: tuple = ()
    number_columns: tuple = ()


def d(date):
    return date.strftime("%d/%m/%Y") if date else "—"


def _period(queryset, field_name, date_from, date_to):
    if date_from:
        queryset = queryset.filter(**{f"{field_name}__gte": date_from})
    if date_to:
        queryset = queryset.filter(**{f"{field_name}__lte": date_to})
    return queryset


def _vehicle_rows(queryset):
    return [[v.registration_number, v.brand, v.model, v.get_category_display(), v.get_fuel_type_display(), v.year,
             v.mileage, v.get_status_display(), d(v.acquisition_date), v.acquisition_price] for v in queryset]


VEHICLE_COLUMNS = ["Immatriculation", "Marque", "Modèle", "Catégorie", "Carburant", "Année", "Kilométrage",
                   "Statut", "Acquisition", "Prix (FCFA)"]


def report_vehicles(date_from, date_to):
    qs = _period(Vehicle.objects.all(), "acquisition_date", date_from, date_to)
    total_value = qs.aggregate(t=Sum("acquisition_price"))["t"] or 0
    return [Section("Liste complète des véhicules", VEHICLE_COLUMNS, _vehicle_rows(qs),
                    ["Total", f"{qs.count()} véhicule(s)", "", "", "", "", "", "", "", total_value],
                    money_columns=(9,), number_columns=(6,))]


def report_available_vehicles(date_from, date_to):
    qs = Vehicle.objects.filter(status=Vehicle.Status.AVAILABLE)
    return [Section("Véhicules disponibles", VEHICLE_COLUMNS, _vehicle_rows(qs),
                    money_columns=(9,), number_columns=(6,))]


def report_immobilized_vehicles(date_from, date_to):
    sections = []
    for status in (Vehicle.Status.IMMOBILIZED, Vehicle.Status.MAINTENANCE, Vehicle.Status.OUT_OF_SERVICE):
        qs = Vehicle.objects.filter(status=status)
        rows = [[v.registration_number, f"{v.brand} {v.model}", v.get_category_display(), v.mileage,
                 d(v.updated_at.date()), v.notes[:80] or "—"] for v in qs]
        sections.append(Section(f"Véhicules — {status.label}",
                                ["Immatriculation", "Véhicule", "Catégorie", "Kilométrage", "Depuis le", "Observations"],
                                rows, number_columns=(3,)))
    return sections


def report_drivers(date_from, date_to):
    qs = _period(Driver.objects.all(), "hire_date", date_from, date_to)
    rows = []
    for drv in qs:
        current = drv.current_assignment
        rows.append([drv.full_name, drv.get_gender_display(), drv.phone, drv.license_number,
                     drv.get_license_category_display(), d(drv.license_expiry_date), d(drv.hire_date),
                     drv.get_status_display(), current.vehicle.registration_number if current else "—"])
    return [Section("Liste des conducteurs",
                    ["Nom et prénom", "Sexe", "Téléphone", "N° permis", "Catégorie", "Expiration permis",
                     "Embauche", "Statut", "Véhicule actuel"], rows)]


def report_assignments(date_from, date_to):
    qs = _period(Assignment.objects.select_related("vehicle", "driver"), "start_date", date_from, date_to)
    rows, distance = [], 0
    for a in qs:
        distance += a.distance or 0
        rows.append([a.vehicle.registration_number, a.driver.full_name, d(a.start_date), d(a.expected_end_date),
                     d(a.actual_return_date), a.start_mileage, a.return_mileage if a.return_mileage is not None else "—",
                     a.distance if a.distance is not None else "—", a.destination or "—", a.get_status_display()])
    return [Section("Historique des affectations",
                    ["Véhicule", "Conducteur", "Début", "Fin prévue", "Retour", "Km départ", "Km retour",
                     "Distance", "Destination", "Statut"], rows,
                    ["Total", f"{len(rows)} affectation(s)", "", "", "", "", "", distance, "", ""],
                    number_columns=(5, 6, 7))]


def report_maintenances(date_from, date_to):
    qs = _period(Maintenance.objects.select_related("vehicle"), "date", date_from, date_to)
    rows = [[d(m.date), m.vehicle.registration_number, m.get_intervention_type_display(), m.provider, m.mileage,
             m.get_status_display(), m.cost] for m in qs]
    return [Section("Historique des entretiens",
                    ["Date", "Véhicule", "Intervention", "Prestataire", "Kilométrage", "Statut", "Coût (FCFA)"], rows,
                    ["Total", "", "", "", "", "", maintenance_services.total_cost(qs)],
                    money_columns=(6,), number_columns=(4,))]


def report_insurances(date_from, date_to):
    qs = _period(Insurance.objects.select_related("vehicle"), "end_date", date_from, date_to)
    rows = [[i.vehicle.registration_number, i.company, i.policy_number, i.get_insurance_type_display(),
             d(i.start_date), d(i.end_date), i.days_remaining, i.state_label, i.premium] for i in qs]
    return [Section("Situation des assurances",
                    ["Véhicule", "Compagnie", "N° police", "Type", "Début", "Expiration", "Jours restants",
                     "État", "Prime (FCFA)"], rows,
                    ["Total", "", "", "", "", "", "", "", qs.aggregate(t=Sum("premium"))["t"] or 0],
                    money_columns=(8,), number_columns=(6,))]


def report_expenses(date_from, date_to):
    qs = _period(Maintenance.objects.all(), "date", date_from, date_to)
    by_vehicle = maintenance_services.cost_by_vehicle(qs)
    total = maintenance_services.total_cost(qs)
    rows = [[r["vehicle__registration_number"], f"{r['vehicle__brand']} {r['vehicle__model']}", r["count"], r["total"],
             f"{(r['total'] / total * 100):.1f} %" if total else "—"] for r in by_vehicle]
    type_labels = dict(Maintenance.InterventionType.choices)
    by_type = qs.exclude(status=Maintenance.Status.CANCELLED).values("intervention_type") \
        .annotate(total=Sum("cost"), count=Count("id")).order_by("-total")
    type_rows = [[type_labels[r["intervention_type"]], r["count"], r["total"]] for r in by_type]
    return [
        Section("Dépenses d'entretien par véhicule", ["Immatriculation", "Véhicule", "Interventions", "Coût total (FCFA)", "Part"],
                rows, ["Total", "", sum(r[2] for r in rows), total, "100 %" if total else "—"],
                money_columns=(3,), number_columns=(2,)),
        Section("Dépenses par type d'intervention", ["Type", "Interventions", "Coût total (FCFA)"], type_rows,
                ["Total", sum(r[1] for r in type_rows), total], money_columns=(2,), number_columns=(1,)),
    ]


def report_fuel(date_from, date_to):
    qs = _period(FuelEntry.objects.select_related("vehicle", "driver"), "date", date_from, date_to)
    rows = [[d(e.date), e.vehicle.registration_number, e.driver.full_name if e.driver else "—", e.mileage,
             f"{e.liters:.2f}".replace(".", ","), e.unit_price, e.total_amount, e.station or "—"] for e in qs]
    total_liters = sum(e.liters for e in qs)
    detail = Section("Pleins de carburant", ["Date", "Véhicule", "Conducteur", "Compteur", "Litres", "Prix/L (FCFA)",
                                             "Montant (FCFA)", "Station"], rows,
                     ["Total", f"{len(rows)} plein(s)", "", "", f"{total_liters:.2f}".replace(".", ","), "",
                      fuel_services.total_amount(qs), ""], money_columns=(5, 6), number_columns=(3,))
    summary_rows = []
    for s in fuel_services.fleet_fuel_summary():
        summary_rows.append([s["vehicle"].registration_number, f"{s['vehicle'].brand} {s['vehicle'].model}", s["entries"],
                             f"{s['total_liters']:.0f}", f"{s['average']}".replace(".", ",") if s["average"] else "—",
                             s["total_amount"]])
    summary = Section("Consommation moyenne par véhicule (toutes périodes)",
                      ["Immatriculation", "Véhicule", "Pleins", "Litres", "L/100 km", "Dépense (FCFA)"], summary_rows,
                      money_columns=(5,), number_columns=(2,))
    return [detail, summary]


def report_claims(date_from, date_to):
    qs = _period(Claim.objects.select_related("vehicle", "driver"), "date", date_from, date_to)
    rows = [[d(c.date), c.vehicle.registration_number, c.get_claim_type_display(), c.location,
             c.driver.full_name if c.driver else "—", c.get_insurance_status_display(), c.final_cost,
             c.indemnity_amount, c.net_cost, c.get_status_display()] for c in qs]
    t = claim_services.totals(qs)
    detail = Section("Sinistres et accidents", ["Date", "Véhicule", "Type", "Lieu", "Conducteur", "Assurance",
                                                "Coût (FCFA)", "Indemnité (FCFA)", "Reste à charge (FCFA)", "Statut"],
                     rows, ["Total", f"{t['count']} sinistre(s)", "", "", "", "", t["cost"], t["indemnity"], t["net"], ""],
                     money_columns=(6, 7, 8))
    types = Section("Répartition par type", ["Type", "Nombre", "Indemnités (FCFA)"],
                    [[r["label"], r["count"], r["indemnity"] or 0] for r in claim_services.by_type(qs)],
                    money_columns=(2,), number_columns=(1,))
    return [detail, types]


def report_costs(date_from, date_to):
    from vehicles.costs import fleet_costs, fleet_totals

    rows = fleet_costs()
    t = fleet_totals(rows)
    data = [[r["vehicle"].registration_number, f"{r['vehicle'].brand} {r['vehicle'].model}", r["acquisition"],
             r["maintenance"], r["fuel"], r["insurance"], r["claims"], r["operating"], r["km"],
             r["per_km"] if r["per_km"] is not None else "—", "À étudier" if r["to_review"] else "—"] for r in rows]
    return [Section("Coût de revient par véhicule (depuis l'acquisition)",
                    ["Immatriculation", "Véhicule", "Achat", "Entretien", "Carburant", "Assurance", "Sinistres",
                     "Exploitation", "Km parcourus", "Coût / km", "Avis"], data,
                    ["Total", f"{len(rows)} véhicule(s)", t["acquisition"], t["maintenance"], t["fuel"], t["insurance"],
                     t["claims"], t["operating"], t["km"], t["per_km"] or "—", ""],
                    money_columns=(2, 3, 4, 5, 6, 7, 9), number_columns=(8,))]


def report_general(date_from, date_to):
    from dashboard.services import get_kpis

    k = get_kpis()
    maint_qs = _period(Maintenance.objects.all(), "date", date_from, date_to)
    summary = Section("Indicateurs clés du parc", ["Indicateur", "Valeur"], [
        ["Nombre total de véhicules", k["total_vehicles"]],
        ["Véhicules disponibles", k["available"]],
        ["Véhicules affectés", k["assigned"]],
        ["Véhicules en entretien", k["in_maintenance"]],
        ["Véhicules immobilisés", k["immobilized"]],
        ["Véhicules hors service", k["out_of_service"]],
        ["Conducteurs (hors inactifs)", k["drivers"]],
        ["Affectations en cours", k["active_assignments"]],
        ["Véhicules avec assurance expirée", k["expired_insurances"]],
        ["Entretiens à effectuer", k["maintenance_due"]],
        ["Alertes non lues", k["unread_alerts"]],
        ["Dépenses d'entretien sur la période (FCFA)", maintenance_services.total_cost(maint_qs)],
        ["Dépenses de carburant sur la période (FCFA)",
         fuel_services.total_amount(_period(FuelEntry.objects.all(), "date", date_from, date_to))],
        ["Valeur d'acquisition du parc (FCFA)", Vehicle.objects.aggregate(t=Sum("acquisition_price"))["t"] or 0],
    ], number_columns=(1,))
    cat_labels = dict(Vehicle.Category.choices)
    categories = Section("Répartition par catégorie", ["Catégorie", "Nombre"], [
        [cat_labels[c], n] for c, n in Vehicle.objects.values_list("category").annotate(n=Count("id")).order_by("-n")
    ], number_columns=(1,))
    alerts = Section("Alertes actives par priorité", ["Priorité", "Nombre"], [
        [label, Alert.objects.filter(is_resolved=False, priority=value).count()]
        for value, label in reversed(Alert.Priority.choices)
    ], number_columns=(1,))
    return [summary, categories, *report_expenses(date_from, date_to)[:1], alerts]


# Registre : clé d'URL -> (titre, description, icône, fonction, filtre de période disponible)
REPORTS = {
    "general": ("Rapport général du parc", "Synthèse des indicateurs, répartition et dépenses.", "clipboard-data", report_general, True),
    "vehicules": ("Liste complète des véhicules", "Tous les véhicules (période = date d'acquisition).", "car-front", report_vehicles, True),
    "vehicules-disponibles": ("Véhicules disponibles", "Véhicules prêts à être affectés.", "check-circle", report_available_vehicles, False),
    "vehicules-immobilises": ("Véhicules immobilisés", "Immobilisés, en entretien et hors service.", "exclamation-octagon", report_immobilized_vehicles, False),
    "conducteurs": ("Liste des conducteurs", "Conducteurs et validité des permis (période = embauche).", "people", report_drivers, True),
    "affectations": ("Historique des affectations", "Affectations et kilomètres parcourus (période = début).", "arrow-left-right", report_assignments, True),
    "entretiens": ("Historique des entretiens", "Interventions et coûts (période = date d'intervention).", "tools", report_maintenances, True),
    "assurances": ("Situation des assurances", "Polices et échéances (période = date d'expiration).", "shield-check", report_insurances, True),
    "carburant": ("Carburant et consommation", "Pleins, litres, dépenses et L/100 km (période = date du plein).", "fuel-pump", report_fuel, True),
    "sinistres": ("Sinistres et accidents", "Sinistres, indemnités et reste à charge (période = date du sinistre).", "exclamation-diamond", report_claims, True),
    "couts": ("Coût de revient des véhicules", "Achat, entretien, carburant, assurance, sinistres et coût au km.", "calculator", report_costs, False),
    "depenses": ("Dépenses d'entretien", "Coûts par véhicule et par type d'intervention.", "cash-coin", report_expenses, True),
}


def build_report(key, date_from=None, date_to=None):
    title, description, icon, func, has_period = REPORTS[key]
    return {
        "key": key, "title": title, "description": description, "has_period": has_period,
        "sections": func(date_from, date_to), "generated_at": timezone.localtime(),
        "date_from": date_from, "date_to": date_to,
    }

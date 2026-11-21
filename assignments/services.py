"""
Logique métier des affectations.

Toutes les règles de gestion sont centralisées ici afin d'être appliquées de la
même façon par les vues, la commande de démonstration et les tests.
"""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from vehicles.models import Vehicle

from .models import Assignment


def check_assignment_rules(vehicle, driver, exclude_pk=None):
    """Vérifie qu'un véhicule peut être affecté au conducteur. Lève ValidationError sinon."""
    errors = {}
    if vehicle.status in Vehicle.NON_ASSIGNABLE_STATUSES:
        errors["vehicle"] = (
            f"Le véhicule {vehicle.registration_number} est « {vehicle.get_status_display()} » "
            "et ne peut pas être affecté."
        )
    active = Assignment.objects.filter(status=Assignment.Status.ACTIVE)
    if exclude_pk:
        active = active.exclude(pk=exclude_pk)
    if active.filter(vehicle=vehicle).exists():
        errors["vehicle"] = f"Le véhicule {vehicle.registration_number} a déjà une affectation en cours."
    if active.filter(driver=driver).exists():
        errors["driver"] = f"{driver.full_name} a déjà un véhicule affecté."
    if driver.status != driver.Status.ACTIVE:
        errors["driver"] = f"{driver.full_name} n'est pas actif (statut : {driver.get_status_display()})."
    elif driver.license_is_expired:
        errors["driver"] = f"Le permis de {driver.full_name} est expiré."
    if errors:
        raise ValidationError(errors)


@transaction.atomic
def create_assignment(assignment):
    """Enregistre une nouvelle affectation et passe le véhicule au statut « Affecté »."""
    # Verrouille la ligne du véhicule pour éviter deux affectations simultanées
    vehicle = Vehicle.objects.select_for_update().get(pk=assignment.vehicle_id)
    check_assignment_rules(vehicle, assignment.driver)
    assignment.status = Assignment.Status.ACTIVE
    assignment.full_clean()
    assignment.save()
    vehicle.status = Vehicle.Status.ASSIGNED
    if assignment.start_mileage > vehicle.mileage:
        vehicle.mileage = assignment.start_mileage
    vehicle.save(update_fields=["status", "mileage", "updated_at"])
    return assignment


@transaction.atomic
def close_assignment(assignment, return_date, return_mileage, notes=""):
    """Enregistre le retour du véhicule et met fin à l'affectation."""
    if assignment.status != Assignment.Status.ACTIVE:
        raise ValidationError("Seule une affectation en cours peut être clôturée.")
    assignment.actual_return_date = return_date or timezone.localdate()
    assignment.return_mileage = return_mileage
    if notes:
        assignment.notes = f"{assignment.notes}\n{notes}".strip()
    assignment.status = Assignment.Status.DONE
    assignment.full_clean()
    assignment.save()
    vehicle = Vehicle.objects.select_for_update().get(pk=assignment.vehicle_id)
    if return_mileage > vehicle.mileage:
        vehicle.mileage = return_mileage
        vehicle.save(update_fields=["mileage", "updated_at"])
    # Le véhicule redevient disponible si aucune autre restriction ne s'applique
    vehicle.refresh_status()
    assignment.vehicle = vehicle
    return assignment


@transaction.atomic
def cancel_assignment(assignment):
    if assignment.status != Assignment.Status.ACTIVE:
        raise ValidationError("Seule une affectation en cours peut être annulée.")
    assignment.status = Assignment.Status.CANCELLED
    assignment.save(update_fields=["status", "updated_at"])
    assignment.vehicle.refresh_status()
    return assignment

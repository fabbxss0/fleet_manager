"""Logique métier des sinistres."""
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone

from vehicles.models import Vehicle

from .models import Claim


def find_context(vehicle, date):
    """Retrouve l'affectation en cours et l'assurance valide à la date du sinistre."""
    assignment = (vehicle.assignments.filter(start_date__lte=date).exclude(status="ANNULEE")
                  .filter(Q(actual_return_date__isnull=True) | Q(actual_return_date__gte=date))
                  .order_by("-start_date").first())
    insurance = vehicle.insurances.filter(start_date__lte=date, end_date__gte=date).order_by("-end_date").first()
    return assignment, insurance


@transaction.atomic
def save_claim(claim, user=None, immobilize=False):
    """
    Enregistre un sinistre :
    - complète automatiquement le conducteur, l'affectation et la police d'assurance à la date du sinistre ;
    - immobilise le véhicule si demandé (dommages empêchant de rouler) ;
    - note la date de clôture.
    """
    is_new = claim.pk is None
    if is_new and user is not None and user.is_authenticated:
        claim.created_by = user
    vehicle = Vehicle.objects.select_for_update().get(pk=claim.vehicle_id)
    if is_new:
        assignment, insurance = find_context(vehicle, claim.date)
        if claim.assignment_id is None and assignment:
            claim.assignment = assignment
        if claim.driver_id is None and assignment:
            claim.driver = assignment.driver
        if claim.insurance_id is None and insurance:
            claim.insurance = insurance
    if claim.status == Claim.Status.CLOSED and claim.closed_at is None:
        claim.closed_at = timezone.localdate()
    elif claim.status != Claim.Status.CLOSED:
        claim.closed_at = None
    claim.full_clean()
    claim.save()
    if immobilize and vehicle.status not in (Vehicle.Status.OUT_OF_SERVICE, Vehicle.Status.IMMOBILIZED):
        vehicle.status = Vehicle.Status.IMMOBILIZED
        vehicle.save(update_fields=["status", "updated_at"])
    return claim


def totals(queryset=None):
    """Synthèse financière d'un ensemble de sinistres."""
    queryset = Claim.objects.all() if queryset is None else queryset
    claims = list(queryset)
    return {
        "count": len(claims),
        "open": sum(1 for c in claims if c.status != Claim.Status.CLOSED),
        "cost": sum((c.final_cost for c in claims), 0),
        "indemnity": sum((c.indemnity_amount for c in claims), 0),
        "net": sum((c.net_cost for c in claims), 0),
    }


def net_cost_for_vehicle(vehicle, date_from=None, date_to=None):
    queryset = vehicle.claims.all()
    if date_from:
        queryset = queryset.filter(date__gte=date_from)
    if date_to:
        queryset = queryset.filter(date__lte=date_to)
    return sum((c.net_cost for c in queryset), 0)


def by_type(queryset=None):
    queryset = Claim.objects.all() if queryset is None else queryset
    labels = dict(Claim.ClaimType.choices)
    return [{"label": labels[r["claim_type"]], **r}
            for r in queryset.values("claim_type").annotate(count=Count("id"), indemnity=Sum("indemnity_amount"))
            .order_by("-count")]

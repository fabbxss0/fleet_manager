from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from alerts.models import Alert
from alerts.services import generate_alerts
from assignments.models import Assignment
from claims.models import Claim
from claims.services import save_claim, totals
from core.testing import make_driver, make_user, make_vehicle, today
from vehicles.models import Vehicle


def claim(vehicle, **kwargs):
    data = dict(vehicle=vehicle, claim_type="ACCIDENT", date=today(), location="Ouaga", description="Choc",
                estimated_cost=Decimal("100000"))
    data.update(kwargs)
    return Claim(**data)


class ClaimTests(TestCase):
    def test_context_completed_automatically(self):
        vehicle, driver = make_vehicle(insured=True), make_driver()
        assignment = Assignment.objects.create(vehicle=vehicle, driver=driver, start_date=today() - timedelta(days=2),
                                               expected_end_date=today() + timedelta(days=2), start_mileage=1, purpose="x")
        c = save_claim(claim(vehicle))
        self.assertEqual(c.driver, driver)
        self.assertEqual(c.assignment, assignment)
        self.assertEqual(c.insurance, vehicle.insurances.get())

    def test_immobilize_vehicle(self):
        vehicle = make_vehicle()
        save_claim(claim(vehicle), immobilize=True)
        vehicle.refresh_from_db()
        self.assertEqual(vehicle.status, Vehicle.Status.IMMOBILIZED)

    def test_net_cost_after_indemnity(self):
        c = save_claim(claim(make_vehicle(insured=True), repair_cost=Decimal("300000"), insurance_status="INDEMNISE",
                             indemnity_amount=Decimal("200000"), status="CLOTURE"))
        self.assertEqual(c.net_cost, Decimal("100000"))
        self.assertEqual(c.closed_at, today())
        self.assertEqual(totals()["net"], Decimal("100000"))

    def test_indemnity_requires_compensated_status(self):
        with self.assertRaises(ValidationError) as ctx:
            save_claim(claim(make_vehicle(), indemnity_amount=Decimal("1000")))
        self.assertIn("indemnity_amount", ctx.exception.message_dict)

    def test_closing_requires_real_cost(self):
        with self.assertRaises(ValidationError) as ctx:
            save_claim(claim(make_vehicle(), status="CLOTURE"))
        self.assertIn("repair_cost", ctx.exception.message_dict)

    def test_insurance_must_cover_vehicle(self):
        other = make_vehicle(insured=True)
        with self.assertRaises(ValidationError):
            save_claim(claim(make_vehicle(), insurance=other.insurances.get()))

    def test_alerts_for_undeclared_and_stale_claims(self):
        vehicle = make_vehicle(insured=True)
        vehicle.insurances.update(start_date=today() - timedelta(days=100), subscription_date=today() - timedelta(days=100))
        save_claim(claim(vehicle, date=today() - timedelta(days=40)))
        generate_alerts()
        keys = set(Alert.objects.filter(category=Alert.Category.CLAIM).values_list("dedup_key", flat=True))
        self.assertEqual({k.split(":")[-1] for k in keys}, {"non_declare", "ouvert"})

    def test_create_through_view(self):
        self.client.force_login(make_user(User.Role.MANAGER))
        vehicle = make_vehicle()
        response = self.client.post(reverse("claims:create"), {
            "vehicle": vehicle.pk, "claim_type": "VOL", "date": today().isoformat(), "location": "Parking",
            "description": "Vol de rétroviseurs", "estimated_cost": 50000, "insurance_status": "NON_DECLARE",
            "indemnity_amount": 0, "status": "OUVERT", "immobilize": "",
        })
        c = Claim.objects.get()
        self.assertRedirects(response, c.get_absolute_url())
        self.assertEqual(self.client.get(reverse("claims:list")).status_code, 200)

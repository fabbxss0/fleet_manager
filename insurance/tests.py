from datetime import timedelta
from decimal import Decimal

from django.test import TestCase

from core.testing import make_vehicle, today
from insurance.forms import InsuranceForm
from insurance.models import Insurance


class InsuranceTests(TestCase):
    def _data(self, vehicle, **overrides):
        data = {"vehicle": vehicle.pk, "company": "Assureur", "policy_number": "p-1", "insurance_type": "RC",
                "subscription_date": "2026-01-01", "start_date": "2026-01-01", "end_date": "2026-12-31",
                "premium": 200000}
        data.update(overrides)
        return data

    def test_state_is_computed_from_dates(self):
        vehicle = make_vehicle()
        expired = Insurance.objects.create(vehicle=vehicle, company="A", policy_number="X1", insurance_type="RC",
                                           subscription_date=today() - timedelta(days=400), start_date=today() - timedelta(days=400),
                                           end_date=today() - timedelta(days=1), premium=Decimal(1))
        expiring = Insurance.objects.create(vehicle=vehicle, company="A", policy_number="X2", insurance_type="RC",
                                            subscription_date=today(), start_date=today(),
                                            end_date=today() + timedelta(days=10), premium=Decimal(1))
        self.assertEqual(expired.state, "expired")
        self.assertEqual(expiring.state, "expiring")

    def test_end_date_after_start_date(self):
        form = InsuranceForm(data=self._data(make_vehicle(), end_date="2025-06-01"))
        self.assertFalse(form.is_valid())
        self.assertIn("end_date", form.errors)

    def test_overlapping_policies_rejected(self):
        vehicle = make_vehicle()
        form = InsuranceForm(data=self._data(vehicle))
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        form = InsuranceForm(data=self._data(vehicle, policy_number="p-2", start_date="2026-06-01", end_date="2027-05-31",
                                             subscription_date="2026-05-20"))
        self.assertFalse(form.is_valid())
        self.assertIn("start_date", form.errors)

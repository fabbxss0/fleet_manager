from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from core.testing import make_user, make_vehicle, today
from vehicles.forms import VehicleForm
from vehicles.models import Vehicle


class VehicleTests(TestCase):
    def setUp(self):
        self.client.force_login(make_user(User.Role.MANAGER))

    def _form_data(self, **overrides):
        data = {
            "registration_number": "11 ab 1234", "brand": "Toyota", "model": "Corolla", "category": "BERLINE",
            "fuel_type": "ESSENCE", "year": 2022, "chassis_number": "jtd123456", "acquisition_date": "2023-01-10",
            "acquisition_price": 15000000, "mileage": 1200, "status": "DISPONIBLE",
        }
        data.update(overrides)
        return data

    def test_add_vehicle_through_view(self):
        response = self.client.post(reverse("vehicles:create"), self._form_data())
        vehicle = Vehicle.objects.get()
        self.assertRedirects(response, vehicle.get_absolute_url())
        # Immatriculation et châssis normalisés en majuscules
        self.assertEqual(vehicle.registration_number, "11 AB 1234")
        self.assertEqual(vehicle.chassis_number, "JTD123456")
        self.assertEqual(vehicle.status, Vehicle.Status.AVAILABLE)

    def test_registration_number_is_unique_in_form(self):
        make_vehicle(registration_number="11 AB 1234")
        form = VehicleForm(data=self._form_data(registration_number="11 ab  1234"))
        self.assertFalse(form.is_valid())
        self.assertIn("registration_number", form.errors)

    def test_registration_number_is_unique_in_database(self):
        make_vehicle(registration_number="11 AB 9999")
        with self.assertRaises(IntegrityError):
            make_vehicle(registration_number="11 AB 9999")

    def test_future_acquisition_date_rejected(self):
        future = today().replace(year=today().year + 1).isoformat()
        form = VehicleForm(data=self._form_data(acquisition_date=future))
        self.assertFalse(form.is_valid())
        self.assertIn("acquisition_date", form.errors)

    def test_mileage_cannot_decrease(self):
        vehicle = make_vehicle(mileage=50000)
        form = VehicleForm(data=self._form_data(mileage=40000, chassis_number=vehicle.chassis_number), instance=vehicle)
        self.assertFalse(form.is_valid())
        self.assertIn("mileage", form.errors)

    def test_search_and_filter(self):
        make_vehicle(registration_number="11 ZZ 0001", brand="Nissan", category="SUV")
        make_vehicle(registration_number="11 ZZ 0002", brand="Toyota", category="PICKUP")
        response = self.client.get(reverse("vehicles:list"), {"q": "nissan"})
        self.assertContains(response, "11 ZZ 0001")
        self.assertNotContains(response, "11 ZZ 0002")
        response = self.client.get(reverse("vehicles:list"), {"category": "PICKUP"})
        self.assertContains(response, "11 ZZ 0002")
        self.assertNotContains(response, "11 ZZ 0001")

    def test_delete_requires_post_and_works_without_history(self):
        vehicle = make_vehicle()
        self.assertEqual(self.client.get(reverse("vehicles:delete", args=[vehicle.pk])).status_code, 405)
        self.client.post(reverse("vehicles:delete", args=[vehicle.pk]))
        self.assertFalse(Vehicle.objects.filter(pk=vehicle.pk).exists())


class VehicleExtraInfoTests(TestCase):
    def test_acquisition_mileage_cannot_exceed_current(self):
        form = VehicleForm(data={
            "registration_number": "11 XX 0001", "brand": "Toyota", "model": "Corolla", "category": "BERLINE",
            "fuel_type": "ESSENCE", "year": 2022, "chassis_number": "X1", "acquisition_date": "2023-01-10",
            "acquisition_price": 1, "mileage": 1000, "acquisition_mileage": 5000, "status": "DISPONIBLE",
        })
        self.assertFalse(form.is_valid())
        self.assertIn("acquisition_mileage", form.errors)

    def test_vignette_alert_and_renewal(self):
        from datetime import timedelta

        from alerts.models import Alert
        from alerts.services import generate_alerts

        vehicle = make_vehicle(vignette_expiry_date=today() + timedelta(days=5))
        generate_alerts()
        alert = Alert.objects.get(category=Alert.Category.TAX)
        self.assertEqual(alert.priority, Alert.Priority.URGENT)
        vehicle.vignette_expiry_date = today() + timedelta(days=365)
        vehicle.save()
        generate_alerts()
        alert.refresh_from_db()
        self.assertTrue(alert.is_resolved)


class VehicleCostTests(TestCase):
    def test_cost_breakdown_and_per_km(self):
        from datetime import timedelta
        from decimal import Decimal

        from claims.models import Claim
        from fuel.models import FuelEntry
        from maintenance.models import Maintenance
        from vehicles.costs import vehicle_costs

        vehicle = make_vehicle(insured=True, mileage=20000, acquisition_mileage=10000,
                               acquisition_date=today() - timedelta(days=730), acquisition_price=Decimal("10000000"))
        Maintenance.objects.create(vehicle=vehicle, intervention_type="VIDANGE", description="x", date=today(),
                                   mileage=20000, provider="G", cost=Decimal("400000"))
        Maintenance.objects.create(vehicle=vehicle, intervention_type="FREINAGE", description="x", date=today(),
                                   mileage=20000, provider="G", cost=Decimal("999999"), status="ANNULE")
        FuelEntry.objects.create(vehicle=vehicle, date=today(), mileage=20000, liters=Decimal("100"),
                                 unit_price=Decimal("700"))
        Claim.objects.create(vehicle=vehicle, claim_type="ACCIDENT", date=today(), location="x", description="x",
                             repair_cost=Decimal("300000"), insurance_status="INDEMNISE", indemnity_amount=Decimal("200000"))
        c = vehicle_costs(vehicle)
        self.assertEqual(c["maintenance"], Decimal("400000"))   # entretien annulé exclu
        self.assertEqual(c["fuel"], Decimal("70000"))
        self.assertEqual(c["insurance"], Decimal("150000"))     # prime de make_vehicle(insured=True)
        self.assertEqual(c["claims"], Decimal("100000"))        # reste à charge
        self.assertEqual(c["operating"], Decimal("720000"))
        self.assertEqual(c["per_km"], Decimal("72"))            # 720 000 / 10 000 km
        self.assertFalse(c["to_review"])

    def test_costs_page(self):
        from accounts.models import User
        from core.testing import make_user

        make_vehicle()
        self.client.force_login(make_user(User.Role.MANAGER))
        self.assertEqual(self.client.get(reverse("vehicles:costs")).status_code, 200)

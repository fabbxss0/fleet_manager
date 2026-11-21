from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from alerts.models import Alert
from alerts.services import generate_alerts
from assignments.models import Assignment
from core.testing import make_driver, make_user, make_vehicle, today
from fuel.models import FuelEntry
from fuel.services import detect_anomalies, save_fuel_entry, vehicle_fuel_summary


def fill(vehicle, mileage, liters, days_ago=0, price=700, **kwargs):
    return save_fuel_entry(FuelEntry(vehicle=vehicle, mileage=mileage, liters=Decimal(str(liters)),
                                     unit_price=Decimal(price), date=today() - timedelta(days=days_ago), **kwargs))


class FuelRulesTests(TestCase):
    def test_total_amount_is_computed_by_server(self):
        entry = fill(make_vehicle(), 10100, 40.5, price=700)
        self.assertEqual(entry.total_amount, Decimal("28350"))

    def test_fill_updates_vehicle_mileage(self):
        vehicle = make_vehicle(mileage=10000)
        fill(vehicle, 10450, 30)
        vehicle.refresh_from_db()
        self.assertEqual(vehicle.mileage, 10450)

    def test_mileage_cannot_go_backwards(self):
        vehicle = make_vehicle()
        fill(vehicle, 12000, 40, days_ago=10)
        with self.assertRaises(ValidationError) as ctx:
            fill(vehicle, 11500, 40, days_ago=2)
        self.assertIn("mileage", ctx.exception.message_dict)

    def test_liters_cannot_exceed_tank(self):
        with self.assertRaises(ValidationError) as ctx:
            fill(make_vehicle(tank_capacity=50), 10100, 70)
        self.assertIn("liters", ctx.exception.message_dict)

    def test_future_date_rejected(self):
        with self.assertRaises(ValidationError):
            fill(make_vehicle(), 10100, 30, days_ago=-3)


class ConsumptionTests(TestCase):
    def test_average_consumption_full_to_full(self):
        vehicle = make_vehicle(mileage=10000)
        fill(vehicle, 10000, 50, days_ago=30)   # premier plein : référence
        fill(vehicle, 10500, 50, days_ago=20)   # 50 L pour 500 km = 10 L/100
        fill(vehicle, 11000, 40, days_ago=10)   # 40 L pour 500 km = 8 L/100
        summary = vehicle_fuel_summary(vehicle)
        self.assertEqual(summary["rows"][1].consumption, Decimal("10.0"))
        self.assertEqual(summary["rows"][2].consumption, Decimal("8.0"))
        self.assertEqual(summary["average"], Decimal("9.0"))  # 90 L / 1000 km
        self.assertEqual(summary["total_amount"], Decimal("98000"))

    def test_anomaly_detected_and_alert_created(self):
        vehicle = make_vehicle(mileage=10000)
        for i, liters in enumerate([40, 40, 41, 39, 65]):  # dernier plein : +60 %
            fill(vehicle, 10000 + i * 400, liters, days_ago=50 - i * 10)
        anomalies = detect_anomalies()
        self.assertEqual(len(anomalies), 1)
        generate_alerts()
        self.assertTrue(Alert.objects.filter(category=Alert.Category.FUEL, vehicle=vehicle).exists())

    def test_no_anomaly_for_regular_consumption(self):
        vehicle = make_vehicle(mileage=10000)
        for i, liters in enumerate([40, 40, 41, 39, 42]):
            fill(vehicle, 10000 + i * 400, liters, days_ago=50 - i * 10)
        self.assertEqual(detect_anomalies(), [])


class FuelViewTests(TestCase):
    def test_manager_can_record_fill(self):
        self.client.force_login(make_user(User.Role.MANAGER))
        vehicle = make_vehicle(mileage=8000)
        response = self.client.post(reverse("fuel:create"), {
            "vehicle": vehicle.pk, "date": today().isoformat(), "mileage": 8200, "liters": "35.5",
            "unit_price": 675, "full_tank": "on",
        })
        self.assertRedirects(response, reverse("fuel:list"))
        self.assertEqual(FuelEntry.objects.get().total_amount, Decimal("23963"))

    def test_driver_declares_fill_for_own_vehicle_only(self):
        user = make_user(User.Role.DRIVER)
        driver = make_driver(user=user)
        mine, other = make_vehicle(mileage=5000), make_vehicle(mileage=7000)
        Assignment.objects.create(vehicle=mine, driver=driver, start_date=today(),
                                  expected_end_date=today() + timedelta(days=2), start_mileage=5000, purpose="x")
        self.client.force_login(user)
        self.client.post(reverse("fuel:driver_declare"), {
            "vehicle": other.pk,  # tentative de forcer un autre véhicule : ignorée
            "date": today().isoformat(), "mileage": 5300, "liters": "30", "unit_price": 700, "full_tank": "on",
        })
        entry = FuelEntry.objects.get()
        self.assertEqual(entry.vehicle, mine)
        self.assertEqual(entry.driver, driver)
        self.assertEqual(self.client.get(reverse("fuel:list")).status_code, 403)

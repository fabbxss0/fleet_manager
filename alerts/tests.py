from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from alerts.models import Alert
from alerts.services import generate_alerts
from assignments.models import Assignment
from core.testing import make_driver, make_user, make_vehicle, today
from insurance.models import Insurance
from vehicles.models import Vehicle


def insurance(vehicle, days_left, number="POL"):
    return Insurance.objects.create(
        vehicle=vehicle, company="Assureur", policy_number=f"{number}{days_left}", insurance_type="RC",
        subscription_date=today() - timedelta(days=300), start_date=today() - timedelta(days=300),
        end_date=today() + timedelta(days=days_left), premium=Decimal("100000"))


class AlertGenerationTests(TestCase):
    def test_insurance_alert_levels(self):
        insurance(make_vehicle(), 25)
        insurance(make_vehicle(), 5)
        insurance(make_vehicle(), -3)
        insurance(make_vehicle(), 200)  # aucune alerte
        generate_alerts()
        priorities = sorted(Alert.objects.filter(category=Alert.Category.INSURANCE).values_list("priority", flat=True))
        self.assertEqual(priorities, [Alert.Priority.WARNING, Alert.Priority.URGENT, Alert.Priority.CRITICAL])

    def test_license_alerts(self):
        make_driver(license_expiry_date=today() + timedelta(days=20))
        make_driver(license_expiry_date=today() + timedelta(days=3))
        make_driver(license_expiry_date=today() - timedelta(days=1))
        generate_alerts()
        self.assertEqual(Alert.objects.filter(category=Alert.Category.LICENSE).count(), 3)
        self.assertTrue(Alert.objects.filter(category=Alert.Category.LICENSE, priority=Alert.Priority.CRITICAL).exists())

    def test_no_duplicates_when_run_twice(self):
        insurance(make_vehicle(), -3)
        make_vehicle(status=Vehicle.Status.IMMOBILIZED)
        first = generate_alerts()
        second = generate_alerts()
        self.assertEqual(first["created"], 2)
        self.assertEqual(second["created"], 0)
        self.assertEqual(Alert.objects.count(), 2)

    def test_alert_resolved_when_situation_disappears(self):
        vehicle = make_vehicle(status=Vehicle.Status.IMMOBILIZED)
        generate_alerts()
        Vehicle.objects.filter(pk=vehicle.pk).update(status=Vehicle.Status.AVAILABLE)
        result = generate_alerts()
        self.assertEqual(result["resolved"], 1)
        self.assertTrue(Alert.objects.get().is_resolved)

    def test_escalation_creates_new_level(self):
        policy = insurance(make_vehicle(), 20)
        generate_alerts()
        Insurance.objects.filter(pk=policy.pk).update(end_date=today() + timedelta(days=4))
        generate_alerts()
        open_alert = Alert.objects.get(is_resolved=False)
        self.assertEqual(open_alert.priority, Alert.Priority.URGENT)

    def test_overdue_assignment_alert(self):
        Assignment.objects.create(vehicle=make_vehicle(status=Vehicle.Status.ASSIGNED), driver=make_driver(),
                                  start_date=today() - timedelta(days=10), expected_end_date=today() - timedelta(days=2),
                                  start_mileage=10000, purpose="Mission")
        generate_alerts()
        self.assertTrue(Alert.objects.filter(category=Alert.Category.ASSIGNMENT).exists())


class AlertViewTests(TestCase):
    def test_mark_as_read_and_counter(self):
        make_vehicle(status=Vehicle.Status.IMMOBILIZED)
        generate_alerts()
        alert = Alert.objects.get()
        self.client.force_login(make_user(User.Role.MANAGER))
        response = self.client.get(reverse("alerts:list"))
        self.assertEqual(response.context["unread_alerts_count"], 1)
        self.client.post(reverse("alerts:toggle_read", args=[alert.pk]))
        alert.refresh_from_db()
        self.assertTrue(alert.is_read)
        response = self.client.get(reverse("alerts:list"))
        self.assertEqual(response.context["unread_alerts_count"], 0)

    def test_management_command(self):
        from io import StringIO

        from django.core.management import call_command

        make_vehicle(status=Vehicle.Status.IMMOBILIZED)
        out = StringIO()
        call_command("generate_alerts", stdout=out)
        self.assertIn("Alertes créées : 1", out.getvalue())

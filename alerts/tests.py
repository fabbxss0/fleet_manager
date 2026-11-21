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
        manager, admin = make_user(User.Role.MANAGER), make_user(User.Role.ADMIN)
        self.client.force_login(manager)
        response = self.client.get(reverse("alerts:list"))
        self.assertEqual(response.context["unread_alerts_count"], 1)
        self.client.post(reverse("alerts:toggle_read", args=[alert.pk]))
        self.assertTrue(alert.is_read_by(manager))
        response = self.client.get(reverse("alerts:list"))
        self.assertEqual(response.context["unread_alerts_count"], 0)
        # Le statut est propre à chaque utilisateur : l'administrateur ne l'a pas encore lue
        self.assertFalse(alert.is_read_by(admin))
        self.client.force_login(admin)
        self.assertEqual(self.client.get(reverse("alerts:list")).context["unread_alerts_count"], 1)

    def test_mark_all_read_only_for_current_user(self):
        make_vehicle(status=Vehicle.Status.IMMOBILIZED)
        make_vehicle(status=Vehicle.Status.IMMOBILIZED)
        generate_alerts()
        manager, other = make_user(User.Role.MANAGER), make_user(User.Role.MANAGER)
        self.client.force_login(manager)
        self.client.post(reverse("alerts:mark_all_read"))
        self.assertEqual(Alert.objects.unread_for(manager).count(), 0)
        self.assertEqual(Alert.objects.unread_for(other).count(), 2)

    def test_management_command(self):
        from io import StringIO

        from django.core.management import call_command

        make_vehicle(status=Vehicle.Status.IMMOBILIZED)
        out = StringIO()
        call_command("generate_alerts", stdout=out)
        self.assertIn("Alertes créées : 1", out.getvalue())


class AlertEmailTests(TestCase):
    def test_digest_sent_once_to_opted_in_staff(self):
        from django.core import mail

        from alerts.notifications import send_alert_emails

        admin = make_user(User.Role.ADMIN)
        admin.email = "admin@exemple.bf"
        admin.save()
        opted_out = make_user(User.Role.MANAGER)
        opted_out.email, opted_out.email_alerts = "non@exemple.bf", False
        opted_out.save()
        driver_user = make_user(User.Role.DRIVER)
        driver_user.email = "conducteur@exemple.bf"
        driver_user.save()
        insurance(make_vehicle(), -2)   # critique -> envoyée
        insurance(make_vehicle(), 20)   # attention -> pas d'email
        generate_alerts()
        result = send_alert_emails()
        self.assertEqual(result, {"alerts": 1, "recipients": 1})
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["admin@exemple.bf"])
        self.assertIn("Assurance expirée", mail.outbox[0].body)
        # deuxième passage : rien de nouveau, aucun email
        self.assertEqual(send_alert_emails()["alerts"], 0)
        self.assertEqual(len(mail.outbox), 1)

    def test_admin_test_email(self):
        from django.core import mail

        admin = make_user(User.Role.ADMIN)
        admin.email = "admin@exemple.bf"
        admin.save()
        self.client.force_login(admin)
        self.client.post(reverse("core:email_test"))
        self.assertEqual(mail.outbox[0].subject, "[FLEET MANAGER] Email de test")

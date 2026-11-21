from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from audit.context import audit_disabled
from audit.models import AuditLog
from core.testing import make_user, make_vehicle
from vehicles.models import Vehicle


class AuditLogTests(TestCase):
    def setUp(self):
        self.manager = make_user(User.Role.MANAGER, username="paul")
        self.client.force_login(self.manager)

    def _vehicle_data(self, **overrides):
        data = {"registration_number": "11 AU 0001", "brand": "Toyota", "model": "Corolla", "category": "BERLINE",
                "fuel_type": "ESSENCE", "year": 2022, "chassis_number": "AUDIT01", "acquisition_date": "2023-01-10",
                "acquisition_price": 15000000, "mileage": 1000, "status": "DISPONIBLE"}
        data.update(overrides)
        return data

    def test_creation_is_logged_with_author(self):
        self.client.post(reverse("vehicles:create"), self._vehicle_data())
        vehicle = Vehicle.objects.get()
        log = AuditLog.for_object(vehicle).get()
        self.assertEqual(log.action, AuditLog.Action.CREATE)
        self.assertEqual(log.user, self.manager)
        self.assertEqual(log.username, "paul")
        self.assertEqual(log.changes["Marque"], ["—", "Toyota"])
        self.assertEqual(log.ip_address, "127.0.0.1")

    def test_modification_records_old_and_new_values(self):
        self.client.post(reverse("vehicles:create"), self._vehicle_data())
        vehicle = Vehicle.objects.get()
        self.client.post(reverse("vehicles:update", args=[vehicle.pk]),
                         self._vehicle_data(mileage=2500, status="IMMOBILISE"))
        log = AuditLog.for_object(vehicle).filter(action=AuditLog.Action.UPDATE).get()
        self.assertEqual(log.changes["Kilométrage actuel"], ["1000", "2500"])
        self.assertEqual(log.changes["Statut"], ["Disponible", "Immobilisé"])
        self.assertNotIn("Marque", log.changes)  # seuls les champs modifiés sont notés

    def test_save_without_change_is_not_logged(self):
        vehicle = make_vehicle()
        vehicle.save()
        self.assertFalse(AuditLog.objects.filter(action=AuditLog.Action.UPDATE).exists())

    def test_deletion_is_logged_and_survives_object(self):
        vehicle = make_vehicle(registration_number="11 DEL 0001")
        self.client.post(reverse("vehicles:delete", args=[vehicle.pk]))
        log = AuditLog.objects.get(action=AuditLog.Action.DELETE)
        self.assertIn("11 DEL 0001", log.object_repr)
        self.assertIsNone(log.target_url)

    def test_password_is_never_logged(self):
        user = make_user(User.Role.MANAGER)
        user.set_password("NouveauMotDePasse#1")
        user.save()
        for log in AuditLog.objects.filter(model_label="accounts.user"):
            self.assertFalse(any("passe" in key.lower() for key in log.changes))

    def test_login_and_failed_login_are_logged(self):
        make_user(username="alice", password="Secret#2026x")
        self.client.logout()
        self.client.post(reverse("accounts:login"), {"username": "alice", "password": "mauvais"})
        self.client.post(reverse("accounts:login"), {"username": "alice", "password": "Secret#2026x"})
        self.assertTrue(AuditLog.objects.filter(action=AuditLog.Action.LOGIN_FAILED, username="alice").exists())
        self.assertTrue(AuditLog.objects.filter(action=AuditLog.Action.LOGIN, username="alice").exists())

    def test_entries_cannot_be_modified(self):
        make_vehicle()
        log = AuditLog.objects.first()
        log.object_repr = "falsifié"
        with self.assertRaises(ValueError):
            log.save()

    def test_disabled_context(self):
        with audit_disabled():
            vehicle = make_vehicle()
        self.assertFalse(AuditLog.for_object(vehicle).exists())

    def test_journal_page_is_admin_only(self):
        self.assertEqual(self.client.get(reverse("audit:list")).status_code, 403)
        self.client.force_login(make_user(User.Role.ADMIN))
        make_vehicle()
        response = self.client.get(reverse("audit:list"), {"action": "CREATION"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Création")

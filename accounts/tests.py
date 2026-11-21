from datetime import timedelta

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from assignments.models import Assignment
from core.testing import make_driver, make_user, make_vehicle, today


class AuthenticationTests(TestCase):
    def test_login_and_password_hashing(self):
        user = make_user(username="alice", password="Secret#2026x")
        self.assertNotEqual(user.password, "Secret#2026x")  # mot de passe haché
        self.assertTrue(user.password.startswith(("pbkdf2_", "argon2", "bcrypt")))
        response = self.client.post(reverse("accounts:login"), {"username": "alice", "password": "Secret#2026x"})
        self.assertRedirects(response, reverse("dashboard:home"), fetch_redirect_response=False)

    def test_wrong_password_shows_french_error(self):
        make_user(username="bob", password="Secret#2026x")
        response = self.client.post(reverse("accounts:login"), {"username": "bob", "password": "faux"})
        self.assertContains(response, "Identifiant ou mot de passe incorrect")

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(reverse("vehicles:list"))
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={reverse('vehicles:list')}")


class PermissionTests(TestCase):
    def test_manager_cannot_manage_users(self):
        self.client.force_login(make_user(User.Role.MANAGER))
        self.assertEqual(self.client.get(reverse("vehicles:list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("accounts:user_list")).status_code, 403)

    def test_admin_can_manage_users(self):
        self.client.force_login(make_user(User.Role.ADMIN))
        self.assertEqual(self.client.get(reverse("accounts:user_list")).status_code, 200)
        response = self.client.post(reverse("accounts:user_create"), {
            "username": "newmanager", "role": "GESTIONNAIRE", "password1": "Complexe#2026!", "password2": "Complexe#2026!",
        })
        self.assertRedirects(response, reverse("accounts:user_list"))
        self.assertTrue(User.objects.filter(username="newmanager", role="GESTIONNAIRE").exists())

    def test_driver_role_is_restricted(self):
        driver_user = make_user(User.Role.DRIVER)
        self.client.force_login(driver_user)
        for name in ("vehicles:list", "drivers:list", "assignments:list", "maintenance:list", "insurance:list",
                     "alerts:list", "reports:index", "dashboard:dashboard"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 403, name)
        self.assertRedirects(self.client.get(reverse("dashboard:home")), reverse("dashboard:driver_space"))

    def test_driver_sees_only_own_vehicle(self):
        user = make_user(User.Role.DRIVER)
        me, other = make_driver(user=user), make_driver()
        my_vehicle, other_vehicle = make_vehicle(registration_number="11 ME 0001"), make_vehicle(registration_number="11 OT 0002")
        for vehicle, driver in ((my_vehicle, me), (other_vehicle, other)):
            Assignment.objects.create(vehicle=vehicle, driver=driver, start_date=today(),
                                      expected_end_date=today() + timedelta(days=2), start_mileage=1, purpose="x")
        self.client.force_login(user)
        response = self.client.get(reverse("dashboard:driver_space"))
        self.assertContains(response, "11 ME 0001")
        self.assertNotContains(response, "11 OT 0002")

    def test_manager_cannot_access_driver_space(self):
        self.client.force_login(make_user(User.Role.MANAGER))
        self.assertEqual(self.client.get(reverse("dashboard:driver_space")).status_code, 403)

    def test_driver_cannot_post_sensitive_actions(self):
        self.client.force_login(make_user(User.Role.DRIVER))
        vehicle = make_vehicle()
        self.client.post(reverse("vehicles:delete", args=[vehicle.pk]))
        self.assertTrue(type(vehicle).objects.filter(pk=vehicle.pk).exists())

    def test_protected_media_requires_login(self):
        response = self.client.get("/media/vehicles/photo.jpg")
        self.assertEqual(response.status_code, 302)

    def test_admin_cannot_demote_himself(self):
        admin = make_user(User.Role.ADMIN)
        self.client.force_login(admin)
        self.client.post(reverse("accounts:user_update", args=[admin.pk]),
                         {"username": admin.username, "role": "GESTIONNAIRE", "is_active": "on"})
        admin.refresh_from_db()
        self.assertEqual(admin.role, User.Role.ADMIN)

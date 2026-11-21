from datetime import timedelta

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from core.testing import make_driver, make_user, today
from drivers.forms import DriverForm
from drivers.models import Driver


class DriverTests(TestCase):
    def setUp(self):
        self.client.force_login(make_user(User.Role.MANAGER))

    def _data(self, **overrides):
        data = {
            "last_name": "Ouédraogo", "first_name": "Awa", "gender": "F", "birth_date": "1990-05-12",
            "phone": "+226 70 11 22 33", "license_number": "bf-123", "license_category": "B",
            "license_issue_date": "2015-03-01", "license_expiry_date": "2030-03-01", "hire_date": "2020-01-06",
            "status": "ACTIF",
        }
        data.update(overrides)
        return data

    def test_add_driver(self):
        response = self.client.post(reverse("drivers:create"), self._data())
        driver = Driver.objects.get()
        self.assertRedirects(response, driver.get_absolute_url())
        self.assertEqual(driver.license_number, "BF-123")

    def test_license_expiry_must_follow_issue_date(self):
        form = DriverForm(data=self._data(license_expiry_date="2014-01-01"))
        self.assertFalse(form.is_valid())
        self.assertIn("license_expiry_date", form.errors)

    def test_driver_must_be_adult(self):
        birth = today().replace(year=today().year - 16).isoformat()
        form = DriverForm(data=self._data(birth_date=birth))
        self.assertFalse(form.is_valid())
        self.assertIn("birth_date", form.errors)

    def test_license_status_helpers(self):
        expired = make_driver(license_expiry_date=today() - timedelta(days=1))
        valid = make_driver()
        self.assertTrue(expired.license_is_expired)
        self.assertFalse(expired.is_assignable)
        self.assertTrue(valid.is_assignable)

    def test_filter_expired_licenses(self):
        expired = make_driver(license_expiry_date=today() - timedelta(days=3))
        valid = make_driver()
        response = self.client.get(reverse("drivers:list"), {"permis": "expire"})
        self.assertContains(response, expired.last_name)
        self.assertNotContains(response, valid.last_name)

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from core.testing import make_user, make_vehicle
from reports.services import REPORTS


class ReportTests(TestCase):
    def setUp(self):
        make_vehicle()
        self.client.force_login(make_user(User.Role.MANAGER))

    def test_every_report_renders_and_exports(self):
        for key in REPORTS:
            url = reverse("reports:detail", args=[key])
            self.assertEqual(self.client.get(url).status_code, 200, key)
            pdf = self.client.get(url, {"format": "pdf"})
            self.assertEqual(pdf["Content-Type"], "application/pdf")
            self.assertTrue(pdf.content.startswith(b"%PDF"))
            xlsx = self.client.get(url, {"format": "xlsx", "du": "2020-01-01", "au": "2030-12-31"})
            self.assertTrue(xlsx.content.startswith(b"PK"))  # un fichier .xlsx est une archive zip

    def test_unknown_report_returns_404(self):
        self.assertEqual(self.client.get(reverse("reports:detail", args=["inconnu"])).status_code, 404)

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from core.testing import make_driver, make_user, make_vehicle
from dashboard.services import get_chart_data, get_kpis
from vehicles.models import Vehicle


class DashboardTests(TestCase):
    def test_kpis_come_from_database(self):
        make_vehicle()
        make_vehicle(status=Vehicle.Status.IMMOBILIZED)
        make_driver()
        kpis = get_kpis()
        self.assertEqual(kpis["total_vehicles"], 2)
        self.assertEqual(kpis["available"], 1)
        self.assertEqual(kpis["immobilized"], 1)
        self.assertEqual(kpis["drivers"], 1)
        charts = get_chart_data()
        self.assertEqual(sum(charts["status"]["values"]), 2)

    def test_dashboard_page(self):
        self.client.force_login(make_user(User.Role.ADMIN))
        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "dashboard-data")

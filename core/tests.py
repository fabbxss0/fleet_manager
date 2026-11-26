from django.test import TestCase

from accounts.models import User
from core.filters import parse_date, parse_int
from core.testing import make_user, make_vehicle


class SafeParametersTests(TestCase):
    """Un paramètre d'URL invalide ne doit jamais produire d'erreur serveur (500)."""

    URLS = [
        "/entretiens/?vehicle=abc", "/entretiens/?du=hier", "/entretiens/?au=2026-99-99", "/entretiens/depenses/?du=abc",
        "/carburant/?vehicle=abc", "/carburant/?du=x", "/assurances/?vehicle=abc", "/sinistres/?vehicle=abc",
        "/sinistres/?du=x", "/alertes/?priorite=abc", "/journal/?user=abc", "/journal/?du=x",
        "/entretiens/nouveau/?vehicle=abc", "/carburant/nouveau/?vehicle=abc", "/vehicules/?status=INCONNU",
        "/affectations/planning/?mois=2026-13", "/rapports/general/?du=abc", "/affectations/nouvelle/?vehicle=abc",
        "/sinistres/nouveau/?vehicle=abc", "/assurances/nouvelle/?vehicle=abc",
    ]

    def test_invalid_parameters_never_crash(self):
        make_vehicle()
        self.client.force_login(make_user(User.Role.ADMIN))
        self.client.raise_request_exception = False
        for url in self.URLS:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_invalid_filter_is_ignored_but_valid_one_applies(self):
        v1, v2 = make_vehicle(registration_number="11 FI 0001"), make_vehicle(registration_number="11 FI 0002")
        from maintenance.models import Maintenance
        from core.testing import today

        for v in (v1, v2):
            Maintenance.objects.create(vehicle=v, intervention_type="VIDANGE", description="x", date=today(),
                                       mileage=v.mileage, provider="G", cost=1)
        self.client.force_login(make_user(User.Role.MANAGER))
        self.assertEqual(self.client.get("/entretiens/?vehicle=abc").context["result_count"], 2)
        self.assertEqual(self.client.get(f"/entretiens/?vehicle={v1.pk}").context["result_count"], 1)

    def test_helpers(self):
        self.assertEqual(parse_int("12"), 12)
        self.assertIsNone(parse_int("abc"))
        self.assertIsNone(parse_int("-3"))
        self.assertIsNone(parse_date("hier"))
        self.assertEqual(str(parse_date("2026-11-21")), "2026-11-21")

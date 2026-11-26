from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from assignments.models import Assignment
from assignments.services import close_assignment, create_assignment
from core.testing import make_driver, make_user, make_vehicle, today
from vehicles.models import Vehicle


def new_assignment(vehicle, driver, **kwargs):
    data = dict(vehicle=vehicle, driver=driver, start_date=today(), expected_end_date=today() + timedelta(days=3),
                start_mileage=vehicle.mileage, purpose="Mission test")
    data.update(kwargs)
    return Assignment(**data)


class AssignmentRulesTests(TestCase):
    def setUp(self):
        self.vehicle = make_vehicle(insured=True, mileage=10000)
        self.driver = make_driver()

    def test_assign_vehicle_sets_status_assigned(self):
        create_assignment(new_assignment(self.vehicle, self.driver))
        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.status, Vehicle.Status.ASSIGNED)

    def test_vehicle_cannot_have_two_active_assignments(self):
        create_assignment(new_assignment(self.vehicle, self.driver))
        with self.assertRaises(ValidationError):
            create_assignment(new_assignment(Vehicle.objects.get(pk=self.vehicle.pk), make_driver()))

    def test_database_constraint_blocks_second_active_assignment(self):
        new_assignment(self.vehicle, self.driver).save()
        with self.assertRaises(IntegrityError), transaction.atomic():
            new_assignment(self.vehicle, make_driver()).save()

    def test_driver_cannot_have_two_vehicles(self):
        create_assignment(new_assignment(self.vehicle, self.driver))
        with self.assertRaises(ValidationError) as ctx:
            create_assignment(new_assignment(make_vehicle(insured=True), self.driver))
        self.assertIn("driver", ctx.exception.message_dict)

    def test_immobilized_vehicle_cannot_be_assigned(self):
        for status in (Vehicle.Status.IMMOBILIZED, Vehicle.Status.MAINTENANCE, Vehicle.Status.OUT_OF_SERVICE):
            vehicle = make_vehicle(insured=True, status=status)
            with self.assertRaises(ValidationError) as ctx:
                create_assignment(new_assignment(vehicle, make_driver()))
            self.assertIn("vehicle", ctx.exception.message_dict)
        self.assertFalse(Assignment.objects.exists())

    def test_uninsured_vehicle_cannot_be_assigned(self):
        uninsured = make_vehicle()
        with self.assertRaises(ValidationError) as ctx:
            create_assignment(new_assignment(uninsured, self.driver))
        self.assertIn("assurance", str(ctx.exception.message_dict["vehicle"]))

    def test_expired_insurance_blocks_assignment(self):
        from insurance.models import Insurance

        Insurance.objects.filter(vehicle=self.vehicle).update(end_date=today() - timedelta(days=1))
        with self.assertRaises(ValidationError):
            create_assignment(new_assignment(self.vehicle, self.driver))

    def test_driver_with_expired_license_cannot_be_assigned(self):
        driver = make_driver(license_expiry_date=today() - timedelta(days=1))
        with self.assertRaises(ValidationError):
            create_assignment(new_assignment(self.vehicle, driver))

    def test_end_date_must_follow_start_date(self):
        with self.assertRaises(ValidationError) as ctx:
            create_assignment(new_assignment(self.vehicle, self.driver, expected_end_date=today() - timedelta(days=2)))
        self.assertIn("expected_end_date", ctx.exception.message_dict)

    def test_return_mileage_cannot_be_lower_than_start(self):
        assignment = create_assignment(new_assignment(self.vehicle, self.driver))
        with self.assertRaises(ValidationError):
            close_assignment(assignment, today(), 9000)

    def test_closing_assignment_frees_vehicle_and_updates_mileage(self):
        assignment = create_assignment(new_assignment(self.vehicle, self.driver))
        close_assignment(assignment, today(), 10450)
        self.vehicle.refresh_from_db()
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, Assignment.Status.DONE)
        self.assertEqual(assignment.distance, 450)
        self.assertEqual(self.vehicle.status, Vehicle.Status.AVAILABLE)
        self.assertEqual(self.vehicle.mileage, 10450)

    def test_closing_keeps_manual_immobilization(self):
        assignment = create_assignment(new_assignment(self.vehicle, self.driver))
        Vehicle.objects.filter(pk=self.vehicle.pk).update(status=Vehicle.Status.IMMOBILIZED)
        assignment.vehicle.refresh_from_db()
        close_assignment(assignment, today(), 10100)
        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.status, Vehicle.Status.IMMOBILIZED)


class AssignmentViewTests(TestCase):
    def setUp(self):
        self.client.force_login(make_user(User.Role.MANAGER))

    def test_create_and_return_through_views(self):
        vehicle, driver = make_vehicle(insured=True, mileage=5000), make_driver()
        response = self.client.post(reverse("assignments:create"), {
            "vehicle": vehicle.pk, "driver": driver.pk, "start_date": today().isoformat(),
            "expected_end_date": (today() + timedelta(days=2)).isoformat(), "start_mileage": 5000,
            "purpose": "Livraison",
        })
        assignment = Assignment.objects.get()
        self.assertRedirects(response, assignment.get_absolute_url())
        response = self.client.post(reverse("assignments:return", args=[assignment.pk]), {
            "return_date": today().isoformat(), "return_mileage": 4000,
        })
        self.assertEqual(response.status_code, 200)  # formulaire réaffiché avec l'erreur
        self.assertContains(response, "ne peut pas être inférieur")
        self.client.post(reverse("assignments:return", args=[assignment.pk]), {
            "return_date": today().isoformat(), "return_mileage": 5200,
        })
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, Assignment.Status.DONE)

    def test_immobilized_vehicle_rejected_by_form(self):
        vehicle = make_vehicle(status=Vehicle.Status.IMMOBILIZED)
        response = self.client.post(reverse("assignments:create"), {
            "vehicle": vehicle.pk, "driver": make_driver().pk, "start_date": today().isoformat(),
            "expected_end_date": today().isoformat(), "start_mileage": vehicle.mileage, "purpose": "Test",
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Assignment.objects.exists())


class ReturnConditionTests(TestCase):
    def test_damage_requires_description(self):
        from assignments.forms import AssignmentReturnForm

        vehicle, driver = make_vehicle(insured=True, mileage=1000), make_driver()
        assignment = create_assignment(new_assignment(vehicle, driver))
        form = AssignmentReturnForm(data={"return_date": today().isoformat(), "return_mileage": 1200,
                                          "return_condition": "IMPORTANT"}, assignment=assignment)
        self.assertFalse(form.is_valid())
        self.assertIn("damage_notes", form.errors)

    def test_fuel_and_condition_saved(self):
        vehicle, driver = make_vehicle(insured=True, mileage=1000), make_driver()
        assignment = create_assignment(new_assignment(vehicle, driver, start_fuel_level=100))
        close_assignment(assignment, today(), 1300, fuel_level=25, condition="LEGER", damage_notes="Rayure")
        assignment.refresh_from_db()
        self.assertEqual(assignment.get_return_fuel_level_display(), "1/4")
        self.assertEqual(assignment.return_condition, "LEGER")


class PlanningTests(TestCase):
    def test_segments_clipped_to_month(self):
        from datetime import date

        from assignments.planning import build_planning

        vehicle, driver = make_vehicle(), make_driver()
        Assignment.objects.create(vehicle=vehicle, driver=driver, start_date=date(2026, 3, 28),
                                  expected_end_date=date(2026, 4, 3), actual_return_date=date(2026, 4, 3),
                                  return_mileage=vehicle.mileage + 10, start_mileage=vehicle.mileage, purpose="x",
                                  status=Assignment.Status.DONE)
        april = build_planning(date(2026, 4, 1))
        row = next(r for r in april["rows"] if r["vehicle"] == vehicle)
        self.assertEqual(row["segments"][0]["col"], 2)    # 1er avril = 1re colonne de jours
        self.assertEqual(row["segments"][0]["span"], 3)   # 1er, 2 et 3 avril
        self.assertEqual(april["days_in_month"], 30)
        self.assertEqual(april["prev"], "2026-03")

    def test_planning_page(self):
        self.client.force_login(make_user(User.Role.MANAGER))
        response = self.client.get(reverse("assignments:planning"), {"mois": "2026-02"})
        self.assertContains(response, "Février 2026")
        self.assertEqual(self.client.get(reverse("assignments:planning"), {"mois": "n'importe"}).status_code, 200)


class ClosedAssignmentEditTests(TestCase):
    def test_closed_assignment_cannot_be_edited(self):
        self.client.force_login(make_user(User.Role.MANAGER))
        vehicle, driver = make_vehicle(insured=True, mileage=1000), make_driver()
        assignment = close_assignment(create_assignment(new_assignment(vehicle, driver, purpose="Mission initiale")),
                                      today(), 1100)
        url = reverse("assignments:update", args=[assignment.pk])
        self.assertRedirects(self.client.get(url), assignment.get_absolute_url())
        self.client.post(url, {"expected_end_date": (today() + timedelta(days=30)).isoformat(), "purpose": "Falsifié"})
        assignment.refresh_from_db()
        self.assertEqual(assignment.purpose, "Mission initiale")

    def test_active_assignment_still_editable(self):
        self.client.force_login(make_user(User.Role.MANAGER))
        assignment = create_assignment(new_assignment(make_vehicle(insured=True), make_driver()))
        url = reverse("assignments:update", args=[assignment.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.post(url, {"expected_end_date": (today() + timedelta(days=5)).isoformat(), "purpose": "Nouveau motif"})
        assignment.refresh_from_db()
        self.assertEqual(assignment.purpose, "Nouveau motif")

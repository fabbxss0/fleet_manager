from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from core.testing import make_vehicle, today
from maintenance.models import Maintenance
from maintenance.services import cost_by_month, cost_by_vehicle, get_due_schedules, save_maintenance, total_cost
from vehicles.models import Vehicle


def maintenance(vehicle, **kwargs):
    data = dict(vehicle=vehicle, intervention_type=Maintenance.InterventionType.OIL_CHANGE, description="Test",
                date=today(), mileage=vehicle.mileage, provider="Garage", cost=Decimal("50000"))
    data.update(kwargs)
    return Maintenance(**data)


class MaintenanceCostTests(TestCase):
    def test_total_cost_by_vehicle_excludes_cancelled(self):
        v1, v2 = make_vehicle(), make_vehicle()
        save_maintenance(maintenance(v1, cost=Decimal("100000")))
        save_maintenance(maintenance(v1, cost=Decimal("250000"), intervention_type="FREINAGE"))
        save_maintenance(maintenance(v1, cost=Decimal("999999"), status=Maintenance.Status.CANCELLED))
        save_maintenance(maintenance(v2, cost=Decimal("40000")))
        self.assertEqual(v1.total_maintenance_cost, Decimal("350000"))
        self.assertEqual(total_cost(), Decimal("390000"))
        rows = list(cost_by_vehicle())
        self.assertEqual(rows[0]["vehicle__id"], v1.pk)
        self.assertEqual(rows[0]["total"], Decimal("350000"))
        self.assertEqual(rows[0]["count"], 2)

    def test_monthly_expenses_cover_twelve_months(self):
        v = make_vehicle()
        save_maintenance(maintenance(v, cost=Decimal("75000")))
        months = cost_by_month(12)
        self.assertEqual(len(months), 12)
        self.assertEqual(months[-1][1], 75000.0)
        self.assertEqual(sum(t for _, t in months), 75000.0)


class MaintenanceStatusTests(TestCase):
    def test_in_progress_maintenance_blocks_vehicle_then_releases_it(self):
        vehicle = make_vehicle()
        m = save_maintenance(maintenance(vehicle, status=Maintenance.Status.IN_PROGRESS))
        vehicle.refresh_from_db()
        self.assertEqual(vehicle.status, Vehicle.Status.MAINTENANCE)
        m.status = Maintenance.Status.DONE
        save_maintenance(m)
        vehicle.refresh_from_db()
        self.assertEqual(vehicle.status, Vehicle.Status.AVAILABLE)

    def test_maintenance_updates_vehicle_mileage(self):
        vehicle = make_vehicle(mileage=10000)
        save_maintenance(maintenance(vehicle, mileage=12500))
        vehicle.refresh_from_db()
        self.assertEqual(vehicle.mileage, 12500)

    def test_next_date_must_follow_intervention(self):
        with self.assertRaises(ValidationError):
            save_maintenance(maintenance(make_vehicle(), next_date=today() - timedelta(days=1)))


class DueScheduleTests(TestCase):
    def test_overdue_and_upcoming_periodic_maintenance(self):
        overdue_vehicle = make_vehicle(mileage=20000)
        soon_vehicle = make_vehicle(mileage=20000)
        ok_vehicle = make_vehicle(mileage=20000)
        save_maintenance(maintenance(overdue_vehicle, date=today() - timedelta(days=200), mileage=14000,
                                     next_date=today() - timedelta(days=10), next_mileage=19000))
        save_maintenance(maintenance(soon_vehicle, date=today() - timedelta(days=170), mileage=19500,
                                     next_date=today() + timedelta(days=5)))
        save_maintenance(maintenance(ok_vehicle, date=today() - timedelta(days=10), mileage=19900,
                                     next_date=today() + timedelta(days=170), next_mileage=24900))
        states = {s["vehicle"].pk: s["state"] for s in get_due_schedules()}
        self.assertEqual(states.get(overdue_vehicle.pk), "overdue")
        self.assertEqual(states.get(soon_vehicle.pk), "soon")
        self.assertNotIn(ok_vehicle.pk, states)

    def test_newer_maintenance_replaces_old_schedule(self):
        vehicle = make_vehicle(mileage=20000)
        save_maintenance(maintenance(vehicle, date=today() - timedelta(days=300), mileage=10000,
                                     next_date=today() - timedelta(days=120)))
        save_maintenance(maintenance(vehicle, date=today() - timedelta(days=5), mileage=19900,
                                     next_date=today() + timedelta(days=180)))
        self.assertEqual(get_due_schedules(), [])

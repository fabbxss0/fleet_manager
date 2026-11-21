"""Fabriques d'objets utilisées par les tests automatisés de toutes les applications."""
from datetime import timedelta
from decimal import Decimal
from itertools import count

from django.utils import timezone

from accounts.models import User
from drivers.models import Driver
from vehicles.models import Vehicle

_seq = count(1)


def today():
    return timezone.localdate()


def make_user(role=User.Role.MANAGER, username=None, password="MotDePasse#2026"):
    username = username or f"user{next(_seq)}"
    return User.objects.create_user(username=username, password=password, role=role)


def make_vehicle(**kwargs):
    n = next(_seq)
    data = dict(
        registration_number=f"11 TT {1000 + n}", brand="Toyota", model="Hilux", category=Vehicle.Category.PICKUP,
        fuel_type=Vehicle.Fuel.DIESEL, year=2021, chassis_number=f"CHASSIS{n:06d}",
        acquisition_date=today() - timedelta(days=400), acquisition_price=Decimal("20000000"), mileage=10000,
    )
    data.update(kwargs)
    return Vehicle.objects.create(**data)


def make_driver(**kwargs):
    n = next(_seq)
    data = dict(
        last_name=f"TEST{n}", first_name="Jean", gender=Driver.Gender.MALE,
        birth_date=today().replace(year=today().year - 30), phone="+226 70 00 00 00",
        license_number=f"PERMIS-{n}", license_category=Driver.LicenseCategory.B,
        license_issue_date=today() - timedelta(days=2000), license_expiry_date=today() + timedelta(days=1000),
        hire_date=today() - timedelta(days=500),
    )
    data.update(kwargs)
    return Driver.objects.create(**data)

"""
Commande : python manage.py seed_demo [--reset]

Remplit la base avec des données FICTIVES et réalistes (dates calculées par
rapport à aujourd'hui pour que les alertes soient pertinentes) :
15 véhicules, 10 conducteurs, affectations, entretiens, assurances, alertes
et trois comptes de démonstration (administrateur, gestionnaire, conducteur).
Aucune information personnelle réelle n'est utilisée.
"""
import random
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from alerts.models import Alert
from alerts.services import generate_alerts
from audit.context import audit_disabled
from audit.models import AuditLog
from assignments.models import Assignment
from assignments.services import create_assignment
from core.models import AppSettings
from drivers.models import Driver
from claims.models import Claim
from claims.services import save_claim
from fuel.models import FuelEntry
from fuel.services import save_fuel_entry
from insurance.models import Insurance
from maintenance.models import Maintenance
from vehicles.models import Vehicle

DEMO_PASSWORDS = {"admin": "Admin@2026", "gestionnaire": "Gestion@2026", "conducteur": "Conducteur@2026"}

# immatriculation, marque, modèle, catégorie, carburant, couleur, année, prix, km, réservoir, CV
VEHICLES = [
    ("11 JK 4521", "Toyota", "Hilux", "PICKUP", "DIESEL", "Blanc", 2021, 24_500_000, 68_400, 80, 12),
    ("11 KL 1078", "Toyota", "Land Cruiser Prado", "SUV", "DIESEL", "Gris", 2020, 38_000_000, 91_200, 87, 15),
    ("11 GH 3390", "Toyota", "Corolla", "BERLINE", "ESSENCE", "Noir", 2022, 16_800_000, 34_750, 50, 8),
    ("11 HM 7712", "Nissan", "Navara", "PICKUP", "DIESEL", "Blanc", 2019, 21_000_000, 122_300, 80, 12),
    ("11 LP 2045", "Mitsubishi", "L200", "PICKUP", "DIESEL", "Argent", 2021, 20_500_000, 57_800, 75, 11),
    ("11 MN 6634", "Hyundai", "Tucson", "SUV", "ESSENCE", "Bleu", 2023, 22_900_000, 18_600, 54, 10),
    ("11 BC 9081", "Peugeot", "508", "BERLINE", "DIESEL", "Gris foncé", 2020, 19_500_000, 76_100, 55, 9),
    ("11 DF 4410", "Mercedes-Benz", "Sprinter", "CAMIONNETTE", "DIESEL", "Blanc", 2018, 27_000_000, 158_900, 75, 13),
    ("11 EG 5527", "Isuzu", "NPR 75", "CAMION", "DIESEL", "Blanc", 2017, 32_000_000, 201_400, 140, 16),
    ("11 FP 3306", "Toyota", "Hiace", "MINIBUS", "DIESEL", "Blanc", 2019, 26_500_000, 134_700, 70, 12),
    ("11 AA 0457", "Yamaha", "Crypton 115", "MOTO", "ESSENCE", "Rouge", 2022, 950_000, 21_300, 4, 1),
    ("11 AB 0458", "Honda", "XR 150", "MOTO", "ESSENCE", "Noir", 2021, 1_350_000, 29_800, 12, 2),
    ("11 RT 8823", "Renault", "Duster", "SUV", "ESSENCE", "Orange", 2022, 14_700_000, 41_900, 50, 8),
    ("11 SU 1199", "Ford", "Ranger", "PICKUP", "DIESEL", "Bleu nuit", 2023, 25_900_000, 15_200, 80, 12),
    ("11 VW 6050", "Suzuki", "Jimny", "AUTRE", "ESSENCE", "Vert", 2016, 9_800_000, 187_500, 40, 7),
]

# nom, prénom, sexe, cat. permis, décalage d'expiration du permis (jours)
DRIVERS = [
    ("KABORÉ", "Issouf", "M", "BCDE", 900),
    ("OUÉDRAOGO", "Aminata", "F", "B", 640),
    ("SAWADOGO", "Rasmané", "M", "BC", 25),      # expire dans moins de 30 jours
    ("TRAORÉ", "Mariam", "F", "B", 1200),
    ("ZONGO", "Boukary", "M", "BCDE", 5),        # expire dans moins de 7 jours
    ("COMPAORÉ", "Salif", "M", "C", 480),
    ("NIKIÉMA", "Clarisse", "F", "B", -12),      # permis expiré
    ("SANOU", "Daouda", "M", "BC", 730),
    ("ILBOUDO", "Hamado", "M", "A", 360),
    ("KONATÉ", "Fatimata", "F", "B", 1500),
]

GARAGES = ["Garage Central Auto", "Atelier Mécanique du Kadiogo", "Auto Service Plus", "Pneus Express",
           "Électro-Auto Diagnostic", "Centre de Contrôle Technique Agréé"]
DEPARTMENTS = ["Direction générale", "Logistique", "Commercial", "Technique", "Ressources humaines"]
COMPANIES = ["Sonar Assurances", "Allianz Burkina", "Jackson Assurances", "Coris Assurances", "UAB Assurances"]
PURPOSES = [("Mission de supervision", "Koudougou"), ("Livraison de matériel", "Bobo-Dioulasso"),
            ("Accompagnement de la direction", "Ouagadougou"), ("Tournée commerciale", "Ouahigouya"),
            ("Formation régionale", "Kaya"), ("Collecte de données terrain", "Fada N'Gourma"),
            ("Courses administratives", "Ouagadougou"), ("Visite de chantier", "Tenkodogo")]


class Command(BaseCommand):
    help = "Remplit la base avec des données de démonstration fictives."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true",
                            help="Supprime d'abord les données du parc (véhicules, conducteurs, etc.) existantes.")

    def handle(self, *args, **options):
        random.seed(2026)
        if Vehicle.objects.exists() and not options["reset"]:
            raise CommandError("La base contient déjà des données. Relancez avec --reset pour les remplacer.")
        # Le chargement initial n'est pas journalisé : le journal commence vide
        with transaction.atomic(), audit_disabled():
            if options["reset"]:
                self._reset()
            self.today = timezone.localdate()
            AppSettings.objects.update_or_create(pk=1, defaults={"organization_name": "Direction Logistique — Démo"})
            vehicles = self._create_vehicles()
            drivers = self._create_drivers()
            self._create_users(drivers)
            self._create_insurances(vehicles)
            self._create_maintenances(vehicles)
            self._create_assignments(vehicles, drivers)
            self._set_special_statuses(vehicles)
            self._create_fuel_entries(vehicles, drivers)
            self._create_claims(vehicles)
        result = generate_alerts()
        # Quelques alertes d'information déjà lues, pour montrer les deux états
        admin = User.objects.get(username="admin")
        for alert in Alert.objects.filter(priority=Alert.Priority.INFO)[:2]:
            alert.mark_read(admin)  # lues par l'administrateur seulement
        self.stdout.write(self.style.SUCCESS(
            f"Données créées : {Vehicle.objects.count()} véhicules, {Driver.objects.count()} conducteurs, "
            f"{Assignment.objects.count()} affectations, {Maintenance.objects.count()} entretiens, "
            f"{Insurance.objects.count()} assurances, {FuelEntry.objects.count()} pleins, {Claim.objects.count()} sinistres, "
            f"{result['open']} alertes."))
        self.stdout.write("Comptes de démonstration :")
        for username, password in DEMO_PASSWORDS.items():
            self.stdout.write(f"  - {username} / {password}")

    def _reset(self):
        Alert.objects.all().delete()
        AuditLog.objects.all().delete()
        Claim.objects.all().delete()
        FuelEntry.objects.all().delete()
        Assignment.objects.all().delete()
        Maintenance.objects.all().delete()
        Insurance.objects.all().delete()
        Driver.objects.all().delete()
        Vehicle.objects.all().delete()
        User.objects.filter(username__in=DEMO_PASSWORDS.keys()).delete()

    def _create_vehicles(self):
        vehicles = []
        for i, (reg, brand, model, cat, fuel, color, year, price, km, tank, cv) in enumerate(VEHICLES):
            acquisition = self.today.replace(year=max(year, self.today.year - 6)) - timedelta(days=30 + i * 11)
            acquisition = max(acquisition, self.today.replace(year=year, month=1, day=15))
            vehicles.append(Vehicle.objects.create(
                registration_number=reg, brand=brand, model=model, category=cat, fuel_type=fuel, color=color,
                year=year, chassis_number=f"DEMO{year}{i:03d}X{random.randint(100000, 999999)}",
                acquisition_date=acquisition, acquisition_price=Decimal(price), mileage=km - 4000,
                tank_capacity=tank, fiscal_power=cv, notes="Véhicule de démonstration.",
                registration_card_number=f"CG-{year}-{4500 + i * 13}",
                first_registration_date=max(acquisition - timedelta(days=20), self.today.replace(year=year, month=1, day=2)),
                # échéances de vignette : la plupart lointaines, une proche et une dépassée
                vignette_expiry_date=self.today + timedelta(days=[120, 200, 18, 90, 150, 240, 60, 300, 100, -15, 180, 210, 75, 280, 330][i]),
                department=DEPARTMENTS[i % len(DEPARTMENTS)],
                seats={"MOTO": 2, "MINIBUS": 18, "CAMION": 3, "CAMIONNETTE": 3}.get(cat, 5),
                transmission="AUTOMATIQUE" if brand in ("Hyundai", "Peugeot") else ("" if cat == "MOTO" else "MANUELLE"),
                acquisition_mileage=0 if year >= self.today.year - 3 else 12 + i * 7,
            ))
        return vehicles

    def _create_drivers(self):
        drivers = []
        for i, (last, first, gender, cat, expiry_offset) in enumerate(DRIVERS):
            birth = self.today.replace(year=self.today.year - (27 + i * 2)) - timedelta(days=i * 37)
            expiry = self.today + timedelta(days=expiry_offset)
            drivers.append(Driver.objects.create(
                last_name=last, first_name=first, gender=gender, birth_date=birth,
                phone=f"+226 70 00 {i:02d} {10 + i:02d}", address=f"Secteur {10 + i}, Ouagadougou",
                email=f"conducteur{i + 1}@exemple.bf", license_number=f"BF-DEMO-{2015 + i}-{1000 + i * 7}",
                license_category=cat, license_issue_date=expiry - timedelta(days=365 * 10),
                license_expiry_date=expiry, hire_date=self.today - timedelta(days=400 + i * 150),
                status=Driver.Status.INACTIVE if i == 8 else Driver.Status.ACTIVE,
                notes="Conducteur fictif (démonstration).",
                employee_number=f"MAT-{2015 + i}-{100 + i:03d}", department=DEPARTMENTS[i % len(DEPARTMENTS)],
                blood_group=["O+", "A+", "B+", "O-", "AB+", "A-", "O+", "B-", "A+", "O+"][i],
                emergency_contact_name=f"Contact d'urgence {i + 1} (fictif)",
                emergency_contact_phone=f"+226 76 00 {i:02d} {20 + i:02d}",
            ))
        return drivers

    def _create_users(self, drivers):
        admin = User.objects.create_user("admin", "admin@exemple.bf", DEMO_PASSWORDS["admin"],
                                         first_name="Awa", last_name="Démo", role=User.Role.ADMIN)
        admin.is_staff = True  # accès à l'interface /admin de Django
        admin.save()
        User.objects.create_user("gestionnaire", "gestion@exemple.bf", DEMO_PASSWORDS["gestionnaire"],
                                 first_name="Paul", last_name="Gestion", role=User.Role.MANAGER)
        driver_user = User.objects.create_user("conducteur", "conducteur1@exemple.bf", DEMO_PASSWORDS["conducteur"],
                                               first_name=drivers[0].first_name, last_name=drivers[0].last_name,
                                               role=User.Role.DRIVER)
        drivers[0].user = driver_user
        drivers[0].save(update_fields=["user"])

    def _create_insurances(self, vehicles):
        # Décalage (jours) de la date d'expiration de la police actuelle de chaque véhicule
        current_end_offsets = [200, 5, 150, -20, 22, 300, 90, 260, -45, 120, 180, 60, 240, 330, -200]
        for i, (vehicle, end_offset) in enumerate(zip(vehicles, current_end_offsets)):
            end = self.today + timedelta(days=end_offset)
            start = end - timedelta(days=365)
            types = list(Insurance.InsuranceType.values)
            Insurance.objects.create(  # police précédente (historique)
                vehicle=vehicle, company=COMPANIES[(i + 2) % len(COMPANIES)], policy_number=f"POL-{2000 + i}-A",
                insurance_type=types[i % 3], subscription_date=start - timedelta(days=380),
                start_date=start - timedelta(days=365), end_date=start - timedelta(days=1),
                premium=Decimal(180_000 + i * 15_000),
            )
            Insurance.objects.create(
                vehicle=vehicle, company=COMPANIES[i % len(COMPANIES)], policy_number=f"POL-{2000 + i}-B",
                insurance_type=types[(i + 1) % 3], subscription_date=start - timedelta(days=10),
                start_date=start, end_date=end, premium=Decimal(195_000 + i * 17_500),
                notes="Renouvellement annuel.",
            )

    def _create_maintenances(self, vehicles):
        T = Maintenance.InterventionType
        costs = {T.OIL_CHANGE: (35_000, 75_000), T.SERVICE: (150_000, 320_000), T.TIRES: (180_000, 520_000),
                 T.MECHANICAL: (90_000, 650_000), T.ELECTRICAL: (40_000, 180_000), T.BRAKES: (60_000, 210_000),
                 T.BATTERY: (65_000, 140_000), T.BODYWORK: (100_000, 450_000)}
        occasional = [T.TIRES, T.MECHANICAL, T.ELECTRICAL, T.BRAKES, T.BATTERY, T.BODYWORK, T.SERVICE]
        for i, vehicle in enumerate(vehicles):
            final_km = vehicle.mileage + 4000  # compteur réel (voir _create_assignments)
            km = int(final_km * 0.4)
            step = int(final_km * 0.12)
            # Interventions ponctuelles réparties sur les 12 derniers mois
            for j in range(2 + i % 3):
                kind = occasional[(i + j) % len(occasional)]
                low, high = costs[kind]
                date = self.today - timedelta(days=330 - j * 95 - i * 3)
                km += step
                Maintenance.objects.create(
                    vehicle=vehicle, intervention_type=kind, description=f"{kind.label} — intervention courante.",
                    date=date, mileage=km, provider=random.choice(GARAGES[:5]),
                    cost=Decimal(round(random.randint(low, high), -3)), status=Maintenance.Status.DONE,
                )
            # Vidange périodique (6 mois / 5 000 km) : certaines échues, d'autres proches, d'autres lointaines
            last_oil_days_ago = [40, 175, 60, 200, 30, 20, 172, 190, 50, 15, 35, 168, 25, 10, 260][i]
            oil_date = self.today - timedelta(days=last_oil_days_ago)
            km_since_oil = [1500, 2200, 1800, 5600, 2500, 1200, 2600, 5600, 3000, 2000, 900, 1500, 4300, 800, 2000][i]
            oil_km = final_km - km_since_oil
            Maintenance.objects.create(
                vehicle=vehicle, intervention_type=T.OIL_CHANGE, description="Vidange moteur + filtre à huile.",
                date=oil_date, mileage=oil_km, provider=GARAGES[0], cost=Decimal(random.randrange(35_000, 75_000, 1000)),
                next_date=oil_date + timedelta(days=182), next_mileage=oil_km + 5000, status=Maintenance.Status.DONE,
            )
            # Contrôle technique annuel
            ct_days_ago = [100, 340, 200, 50, 355, 120, 30, 380, 150, 330, 90, 60, 210, 15, 400][i]
            ct_date = self.today - timedelta(days=ct_days_ago)
            Maintenance.objects.create(
                vehicle=vehicle, intervention_type=T.TECHNICAL_CONTROL, description="Contrôle technique réglementaire.",
                date=ct_date, mileage=vehicle.mileage - 2000, provider=GARAGES[5], cost=Decimal(25_000),
                next_date=ct_date + timedelta(days=365), status=Maintenance.Status.DONE,
            )
        # Un entretien planifié à venir
        Maintenance.objects.create(
            vehicle=vehicles[1], intervention_type=T.SERVICE, description="Révision des 100 000 km.",
            date=self.today + timedelta(days=12), mileage=vehicles[1].mileage, provider=GARAGES[2],
            cost=Decimal(280_000), status=Maintenance.Status.PLANNED,
        )

    def _create_assignments(self, vehicles, drivers):
        # Affectations terminées (historique)
        history = [(0, 0), (2, 1), (3, 2), (4, 3), (6, 5), (9, 7), (12, 9), (13, 1), (1, 0), (5, 3), (10, 8), (7, 5)]
        for n, (v_index, d_index) in enumerate(history):
            vehicle, driver = vehicles[v_index], drivers[d_index]
            start = self.today - timedelta(days=300 - n * 22)
            duration = 3 + n % 6
            distance = 180 + n * 95
            purpose, destination = PURPOSES[n % len(PURPOSES)]
            Assignment.objects.create(
                vehicle=vehicle, driver=driver, start_date=start, expected_end_date=start + timedelta(days=duration),
                actual_return_date=start + timedelta(days=duration + (1 if n % 4 == 0 else 0)),
                start_mileage=vehicle.mileage - 3800 + n * 10, return_mileage=vehicle.mileage - 3800 + n * 10 + distance,
                purpose=purpose, destination=destination, status=Assignment.Status.DONE,
                start_fuel_level=100, return_fuel_level=[25, 50, 75, 25][n % 4],
                return_condition="LEGER" if n == 5 else "RAS",
                damage_notes="Rayure sur la portière arrière gauche." if n == 5 else "",
            )
        Assignment.objects.create(
            vehicle=vehicles[4], driver=drivers[7], start_date=self.today - timedelta(days=60),
            expected_end_date=self.today - timedelta(days=55), start_mileage=vehicles[4].mileage - 900,
            purpose="Mission annulée (intempéries)", destination="Dori", status=Assignment.Status.CANCELLED,
        )
        for vehicle in vehicles:  # remet les compteurs à la valeur réelle
            vehicle.mileage += 4000
            vehicle.save(update_fields=["mileage"])
        # Affectations en cours (via le service métier, qui applique toutes les règles)
        active = [(0, 0, 2, 5), (1, 1, 10, -3), (2, 3, 1, 12), (5, 5, 4, 2), (13, 9, 6, 20)]
        for n, (v_index, d_index, days_ago, end_in) in enumerate(active):
            purpose, destination = PURPOSES[(n + 3) % len(PURPOSES)]
            vehicle = Vehicle.objects.get(pk=vehicles[v_index].pk)
            create_assignment(Assignment(
                vehicle=vehicle, driver=drivers[d_index], start_date=self.today - timedelta(days=days_ago),
                expected_end_date=self.today + timedelta(days=end_in), start_mileage=vehicle.mileage, start_fuel_level=100,
                purpose=purpose, destination=destination,
            ))

    def _set_special_statuses(self, vehicles):
        # Véhicule en atelier (entretien en cours)
        from maintenance.services import save_maintenance

        save_maintenance(Maintenance(
            vehicle=Vehicle.objects.get(pk=vehicles[7].pk), intervention_type=Maintenance.InterventionType.MECHANICAL,
            description="Remplacement de l'embrayage.", date=self.today - timedelta(days=2),
            mileage=vehicles[7].mileage, provider=GARAGES[1], cost=Decimal(385_000),
            status=Maintenance.Status.IN_PROGRESS,
        ))
        Vehicle.objects.filter(pk=vehicles[8].pk).update(
            status=Vehicle.Status.IMMOBILIZED, notes="Immobilisé : assurance expirée et pont arrière à reprendre.")
        Vehicle.objects.filter(pk=vehicles[14].pk).update(
            status=Vehicle.Status.OUT_OF_SERVICE, notes="Réformé : coût de remise en état trop élevé.")

    def _create_fuel_entries(self, vehicles, drivers):
        """Pleins des 6 derniers mois ; le dernier plein du 11 JK 4521 simule une consommation anormale."""
        # index du véhicule -> (consommation habituelle L/100 km, prix du litre)
        profiles = {0: (10.5, 675), 1: (12.8, 675), 2: (7.2, 850), 5: (8.4, 850), 13: (10.1, 675),
                    3: (11.0, 675), 6: (7.8, 675), 9: (13.5, 675), 12: (8.9, 850)}
        stations = ["Total Ouaga 2000", "Shell Kwamé N'Krumah", "Oryx Gounghin", "Total Tampouy", "SONABHY Relais"]
        for index, (consumption, price) in profiles.items():
            vehicle = Vehicle.objects.get(pk=vehicles[index].pk)
            current = vehicle.current_assignment
            driver = current.driver if current else drivers[index % len(drivers)]
            fills, km = 8, vehicle.mileage - 8 * 420
            for n in range(fills):
                km += 380 + (n * 37) % 90
                rate = consumption * (1 + ((n * 7) % 5 - 2) / 100)  # petites variations réalistes
                if index == 0 and n == fills - 1:
                    rate = consumption * 1.55  # anomalie volontaire
                liters = Decimal(str(round((380 + (n * 37) % 90) * rate / 100, 2)))
                save_fuel_entry(FuelEntry(
                    vehicle=vehicle, driver=driver, date=self.today - timedelta(days=(fills - n) * 21),
                    mileage=min(km, vehicle.mileage), liters=liters, unit_price=Decimal(price),
                    station=stations[(index + n) % len(stations)], full_tank=True,
                ))

    def _create_claims(self, vehicles):
        """Trois sinistres : un clôturé et indemnisé, un non déclaré, un qui traîne en réparation."""
        damaged = Assignment.objects.filter(return_condition="LEGER").first()
        if damaged:
            save_claim(Claim(
                vehicle=damaged.vehicle, assignment=damaged, driver=damaged.driver, claim_type="ACCIDENT",
                date=damaged.actual_return_date, location="Avenue Kwame N'Krumah, Ouagadougou",
                description="Accrochage à faible vitesse lors d'un stationnement : portière arrière rayée.",
                third_party_involved=True, police_report_number="CONSTAT-AMIABLE-0142",
                estimated_cost=Decimal(180_000), repair_cost=Decimal(165_000), insurance_status="INDEMNISE",
                insurance_claim_number="DOS-2026-0571", indemnity_amount=Decimal(115_000), status="CLOTURE",
            ))
        save_claim(Claim(
            vehicle=Vehicle.objects.get(pk=vehicles[8].pk), claim_type="ACCIDENT", date=self.today - timedelta(days=8),
            location="RN1, sortie de Sabou", description="Sortie de route sur chaussée glissante. Pont arrière endommagé.",
            injuries=False, police_report_number="PV-GN-2026-0388", estimated_cost=Decimal(1_450_000),
            insurance_status="NON_DECLARE", status="OUVERT",
        ))
        save_claim(Claim(
            vehicle=Vehicle.objects.get(pk=vehicles[3].pk), claim_type="BRIS_GLACE", date=self.today - timedelta(days=41),
            location="Marché de Rood Woko", description="Pare-brise fissuré par un projectile.",
            estimated_cost=Decimal(260_000), insurance_status="EN_COURS", insurance_claim_number="DOS-2026-0612",
            status="EN_REPARATION",
        ))

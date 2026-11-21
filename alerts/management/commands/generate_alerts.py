"""
Commande : python manage.py generate_alerts

Vérifie toutes les échéances (assurances, permis, entretiens, contrôles
techniques, véhicules immobilisés, retours en retard) et crée les alertes
manquantes sans doublon. À planifier une fois par jour (voir README).
"""
from django.core.management.base import BaseCommand

from alerts.services import generate_alerts


class Command(BaseCommand):
    help = "Génère les alertes automatiques à partir des échéances du parc automobile."

    def handle(self, *args, **options):
        result = generate_alerts()
        self.stdout.write(self.style.SUCCESS(
            f"Alertes créées : {result['created']} | résolues : {result['resolved']} | "
            f"ouvertes : {result['open']}"
        ))

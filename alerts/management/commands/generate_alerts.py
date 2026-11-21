"""
Commande : python manage.py generate_alerts [--sans-email]

Vérifie toutes les échéances (assurances, permis, vignettes, entretiens,
contrôles techniques, véhicules immobilisés, retours en retard, carburant,
sinistres), crée les alertes manquantes sans doublon, puis envoie par email
le récapitulatif des nouvelles alertes urgentes et critiques.
À planifier une fois par jour (voir README).
"""
from django.core.management.base import BaseCommand

from alerts.notifications import send_alert_emails
from alerts.services import generate_alerts


class Command(BaseCommand):
    help = "Génère les alertes automatiques puis envoie les nouvelles alertes urgentes par email."

    def add_arguments(self, parser):
        parser.add_argument("--sans-email", action="store_true", help="Ne pas envoyer d'email.")

    def handle(self, *args, **options):
        result = generate_alerts()
        self.stdout.write(self.style.SUCCESS(
            f"Alertes créées : {result['created']} | résolues : {result['resolved']} | "
            f"ouvertes : {result['open']}"
        ))
        if not options["sans_email"]:
            sent = send_alert_emails()
            self.stdout.write(f"Emails : {sent['alerts']} alerte(s) envoyée(s) à {sent['recipients']} destinataire(s).")

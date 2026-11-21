# FLEET MANAGER — Application de gestion intelligente d'un parc automobile

Application web Django de gestion de flotte : véhicules, conducteurs, affectations,
entretiens, assurances, **alertes automatiques**, tableau de bord et rapports PDF / Excel.

- Langue : français · Devise : Franc CFA (FCFA) · Dates : JJ/MM/AAAA · Fuseau : Africa/Ouagadougou
- Python 3.10+ · Django 5.2 · SQLite (PostgreSQL possible) · Bootstrap 5 · Chart.js
- Toutes les ressources front (Bootstrap, icônes, Chart.js, police Inter) sont **incluses localement** :
  l'application fonctionne sans connexion Internet (pratique pour une soutenance).

---

## 1. Installation sous Windows

Prérequis : Python 3.10 ou plus récent ([python.org](https://www.python.org/downloads/), cocher « Add Python to PATH »).

Ouvrir **PowerShell** ou l'**Invite de commandes** dans le dossier `fleet_manager`, puis :

```bat
python -m venv venv
```

```bat
venv\Scripts\activate
```

```bat
pip install -r requirements.txt
```

```bat
python manage.py migrate
```

```bat
python manage.py seed_demo
```

```bat
python manage.py runserver
```

Ouvrir ensuite <http://127.0.0.1:8000> dans le navigateur.

> Raccourci : double-cliquer sur `lancer.bat` fait toutes ces étapes au premier lancement,
> puis démarre simplement le serveur les fois suivantes.
>
> Sous PowerShell, si l'activation est bloquée : `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

Sous Linux / macOS, remplacer `venv\Scripts\activate` par `source venv/bin/activate`.

## 2. Comptes de démonstration

| Rôle           | Identifiant    | Mot de passe      | Accès |
|----------------|----------------|-------------------|-------|
| Administrateur | `admin`        | `Admin@2026`      | Tout, dont la gestion des utilisateurs, les paramètres et `/admin` |
| Gestionnaire   | `gestionnaire` | `Gestion@2026`    | Véhicules, conducteurs, affectations, entretiens, assurances, alertes, rapports |
| Conducteur     | `conducteur`   | `Conducteur@2026` | Son profil, son véhicule affecté, son historique |

Réinitialiser les données de démonstration : `python manage.py seed_demo --reset`
(supprime uniquement les données du parc et les trois comptes de démo).

## 3. Commandes utiles

| Commande | Rôle |
|---|---|
| `python manage.py runserver` | Démarre le serveur de développement |
| `python manage.py seed_demo [--reset]` | Données fictives : 15 véhicules, 10 conducteurs, affectations, entretiens, assurances, alertes |
| `python manage.py generate_alerts` | Vérifie toutes les échéances et crée les alertes manquantes (sans doublon) |
| `python manage.py test` | Lance les 69 tests automatisés |
| `python manage.py createsuperuser` | Crée un administrateur supplémentaire |

### Génération des alertes

Les alertes sont produites par `alerts/services.py`, de deux façons :

1. **Automatiquement pendant la navigation** : le middleware `AlertAutoRefreshMiddleware` relance
   la vérification au plus une fois toutes les 10 minutes (`ALERTS_AUTO_REFRESH_MINUTES` dans `config/settings.py`).
2. **Par la commande** `python manage.py generate_alerts`, à planifier une fois par jour :
   - **Windows** — Planificateur de tâches → *Créer une tâche de base* → Quotidien, 06:00 →
     Programme : `C:\chemin\fleet_manager\venv\Scripts\python.exe`,
     Arguments : `manage.py generate_alerts`, Démarrer dans : `C:\chemin\fleet_manager`.
   - **Linux** — crontab : `0 6 * * * cd /chemin/fleet_manager && venv/bin/python manage.py generate_alerts`

Le bouton **« Vérifier les échéances »** de la page Alertes lance aussi la vérification immédiatement.

## 4. Architecture

```
fleet_manager/
├── config/          Paramètres Django (settings.py) et routes principales (urls.py)
├── core/            Code partagé : permissions par rôle, mixins de vues, validateurs de fichiers,
│                    filtres de template (FCFA, km, badges), paramètres de l'appli, recherche globale,
│                    médias protégés, commande seed_demo
├── accounts/        Utilisateur personnalisé (champ role), connexion, profil, gestion des comptes
├── vehicles/        Véhicules
├── drivers/         Conducteurs
├── assignments/     Affectations + services.py (règles de gestion)
├── maintenance/     Entretiens + services.py (statut du véhicule, échéances, dépenses)
├── insurance/       Assurances
├── fuel/            Carburant : pleins, consommation (services.py)
├── alerts/          Alertes + services.py (moteur de règles) + middleware + commande generate_alerts
├── dashboard/       Tableau de bord, statistiques (services.py) et espace conducteur
├── reports/         Rapports : services.py (définitions) + exporters.py (PDF et Excel)
├── templates/       Gabarits HTML (base.html + un dossier par module)
└── static/          CSS / JS de l'application + bibliothèques front locales (vendor/)
```

Chaque module suit la même séparation : `models.py` (données et contraintes), `forms.py`
(validation des saisies), `services.py` (logique métier), `views.py` (requêtes HTTP),
`urls.py` (routes), `templates/<module>/` (affichage), `tests.py` (tests).

## 5. Base de données

```
User 1───0..1 Driver 1───* Assignment *───1 Vehicle
                                              │ 1
                       ┌──────────────────────┼──────────────────────┐
                       * Maintenance          * Insurance            * Alert
Alert *──0..1 Driver / Assignment / Insurance / Maintenance / Vehicle
AppSettings (une seule ligne : seuils d'alerte, nom de l'organisation)
```

| Table | Clés et contraintes principales |
|---|---|
| `accounts_user` | PK id · `username` unique · `role` ∈ {ADMIN, GESTIONNAIRE, CONDUCTEUR} · mot de passe haché (PBKDF2) |
| `vehicles_vehicle` | PK id · `registration_number` **unique** · `chassis_number` unique · `status` |
| `drivers_driver` | PK id · `license_number` unique · `user` OneToOne (SET_NULL) · CHECK expiration > délivrance |
| `assignments_assignment` | FK `vehicle`, `driver` (**PROTECT**) · **une seule affectation EN_COURS par véhicule** et **par conducteur** (index uniques conditionnels) · CHECK fin ≥ début · CHECK km retour ≥ km départ |
| `fuel_fuelentry` | FK `vehicle` (PROTECT), `driver` (SET_NULL) · litres > 0 · montant calculé · index (vehicle, mileage) |
| `maintenance_maintenance` | FK `vehicle` (PROTECT) · coût ≥ 0 · index (vehicle, type, date) |
| `insurance_insurance` | FK `vehicle` (PROTECT) · `policy_number` unique · CHECK expiration > début |
| `alerts_alert` | FK facultatives vers l'élément concerné (CASCADE) · `dedup_key` **unique parmi les alertes non résolues** |
| `core_appsettings` | Ligne unique (pk = 1) |

**Conservation de l'historique** : les clés étrangères des affectations, entretiens et assurances
sont en `PROTECT`. Un véhicule ou un conducteur qui a un historique ne peut donc pas être supprimé ;
l'application affiche un message et propose le statut « Hors service » / « Inactif ».
Les contraintes sont posées en base : elles restent valables même si le code est contourné.

**Passage à PostgreSQL** : `pip install "psycopg[binary]"`, définir les variables d'environnement
`DB_ENGINE=postgresql`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, puis `python manage.py migrate`.
Aucune modification du code n'est nécessaire.

## 6. Règles de gestion

**Véhicules**
- L'immatriculation est unique (normalisée en majuscules).
- Le kilométrage ne peut jamais diminuer ; la date d'acquisition ne peut pas être dans le futur ni avant l'année de fabrication.
- « Affecté » et « En entretien » sont des statuts **automatiques** ; « Disponible », « Immobilisé » et « Hors service » se choisissent à la main.

**Affectations** (`assignments/services.py`)
- Un véhicule ne peut pas avoir deux affectations actives ; un conducteur ne peut pas avoir deux véhicules.
- Un véhicule en entretien, immobilisé ou hors service ne peut pas être affecté.
- Le véhicule doit être couvert par une **assurance valide** le jour de l'affectation.
- Le conducteur doit être actif et avoir un permis valide.
- Le kilométrage au départ ne peut pas être inférieur au compteur ; au retour, il ne peut pas être inférieur au départ.
- Au retour, le compteur du véhicule est mis à jour et le véhicule redevient disponible,
  sauf s'il a été immobilisé, mis hors service ou s'il est en entretien.
- Une affectation peut être annulée : elle reste dans l'historique avec le statut « Annulée ».

**Entretiens** (`maintenance/services.py`)
- Un entretien « En cours » passe le véhicule « En entretien » ; terminé, le véhicule retrouve son statut normal.
- Entretien périodique : on renseigne la date et/ou le kilométrage du prochain entretien. Le dernier entretien
  terminé de chaque type par véhicule définit l'échéance. Il est signalé « bientôt » 15 jours / 1 000 km avant
  (seuils réglables) et « dépassé » ensuite.
- Le coût total exclut les interventions annulées.

**Assurances**
- Deux polices d'un même véhicule ne peuvent pas se chevaucher dans le temps.
- La page Assurances liste les véhicules en service sans assurance valide.

**Carburant** (`fuel/services.py`)
- Le montant d'un plein est toujours calculé par le serveur : litres × prix du litre.
- Le compteur d'un plein doit être cohérent avec les pleins précédent et suivant ; la quantité ne peut pas dépasser la capacité du réservoir (+5 %).
- Consommation calculée « du plein à plein » : litres d'un plein complet ÷ km parcourus depuis le plein précédent × 100.
- Si le dernier plein dépasse de plus de 30 % la moyenne du véhicule (au moins 3 mesures), une alerte « Consommation anormale » est créée.
- Un conducteur peut déclarer un plein, uniquement pour le véhicule qui lui est affecté.

**Alertes** (`alerts/services.py`)

| Situation | Priorité |
|---|---|
| Assurance / permis expirant sous 30 jours | Attention |
| Assurance / permis expirant sous 7 jours | Urgent |
| Assurance / permis expiré | Critique |
| Entretien prochainement nécessaire | Information |
| Entretien dépassé | Urgent |
| Contrôle technique à renouveler (30 j) / dépassé | Attention / Critique |
| Véhicule immobilisé | Attention |
| Retour d'affectation en retard (plus de 3 jours) | Attention (Urgent) |
| Consommation de carburant anormale (+30 %) | Attention |

Chaque alerte a une **clé de déduplication** (ex. `insurance:12:j7`) : relancer la génération
ne crée jamais de doublon. Quand la situation disparaît (assurance renouvelée, véhicule réparé),
l'alerte passe automatiquement en « résolue » et rejoint l'historique.

## 7. Sécurité

- Protection CSRF sur tous les formulaires ; suppressions et actions sensibles uniquement en POST.
- Mots de passe hachés par Django (PBKDF2), validateurs de robustesse (8 caractères minimum, etc.).
- Contrôle des rôles **côté serveur** sur chaque vue (`core/permissions.py`) : erreur 403 sinon.
- Toutes les validations sont faites par Django (formulaires, `clean()` des modèles, contraintes SQL) ;
  le JavaScript n'apporte que du confort.
- Fichiers téléversés : extension, taille (photos 2 Mo, documents 5 Mo), contenu vérifié (Pillow pour
  les images, signature `%PDF-` pour les PDF), servis **uniquement aux utilisateurs connectés**.
- Confirmation par fenêtre modale avant toute suppression.
- En production : définir `DJANGO_DEBUG=0`, `DJANGO_SECRET_KEY` et `DJANGO_ALLOWED_HOSTS`.

## 8. Tests

```bat
python manage.py test
```

69 tests couvrent : ajout de véhicule, unicité de l'immatriculation (formulaire et base), ajout de conducteur,
affectation, refus de deux affectations actives (service et contrainte SQL), refus d'un véhicule immobilisé /
en entretien / hors service, validation des dates et kilométrages, génération des alertes (niveaux, absence de
doublons, résolution, escalade), permissions des trois rôles, calcul des dépenses d'entretien, échéances
périodiques, tableau de bord et exports PDF / Excel de tous les rapports.

## 9. Fonctionnalités

- **Tableau de bord** : 10 indicateurs cliquables, 5 graphiques Chart.js (catégories, statuts, dépenses mensuelles,
  coût par véhicule, alertes par priorité), alertes urgentes, prochaines échéances, dernières affectations et entretiens.
- **Véhicules** : CRUD, photo, recherche, filtres (catégorie, statut, carburant), fiche avec historique chronologique.
- **Conducteurs** : CRUD, photo, suivi de l'expiration du permis, historique des affectations et distance parcourue.
- **Affectations** : création guidée (seuls les véhicules et conducteurs éligibles sont proposés), retour, annulation, retards.
- **Entretiens** : historique filtrable par période, « à prévoir », dépenses par véhicule, par type et par mois, justificatifs.
- **Carburant** : saisie des pleins (par le gestionnaire ou le conducteur), consommation L/100 km par véhicule, dépenses mensuelles, détection des consommations anormales.
- **Assurances** : CRUD, états (valide / expire bientôt / expirée), historique par véhicule, renouvellement en un clic.
- **Alertes** : compteur et menu de notifications, page filtrable, lu / non lu, historique des alertes résolues.
- **Rapports** : 10 rapports, filtre par période, aperçu, export PDF et Excel mis en forme, date de génération.
- **Utilisateurs** (administrateur) : création, rôles, rattachement à une fiche conducteur, réinitialisation du mot de passe.
- **Paramètres** : nom de l'organisation et seuils des alertes ; **recherche globale** dans la barre supérieure.
- Interface responsive (ordinateur, tablette, smartphone).

Le fichier [DOCUMENTATION_CODE.md](DOCUMENTATION_CODE.md) explique les parties importantes du code
pour préparer la soutenance.

# Comprendre et défendre le code de FLEET MANAGER

Ce guide parcourt les parties du code qu'un enseignant risque de vous demander d'expliquer.
Pour chaque partie : **où** elle se trouve, **ce qu'elle fait**, **pourquoi** elle est écrite ainsi.

---

## 1. Le cycle d'une requête Django

1. Le navigateur appelle une URL, par exemple `/vehicules/12/`.
2. `config/urls.py` envoie tout ce qui commence par `vehicules/` vers `vehicles/urls.py`.
3. `vehicles/urls.py` associe `<int:pk>/` à la vue `VehicleDetailView` (12 devient `pk`).
4. La vue vérifie les droits (`StaffRequiredMixin`), lit la base via l'ORM et prépare un **contexte**.
5. Le template `templates/vehicles/vehicle_detail.html` transforme ce contexte en HTML.

Les **middlewares** (`MIDDLEWARE` dans `settings.py`) s'exécutent à chaque requête : session,
authentification, protection CSRF… et notre middleware de rafraîchissement des alertes.

## 2. Le modèle utilisateur et les rôles

**Fichier** : `accounts/models.py`

```python
class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Administrateur"
        MANAGER = "GESTIONNAIRE", "Gestionnaire"
        DRIVER = "CONDUCTEUR", "Conducteur"
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MANAGER)
```

- On **hérite** d'`AbstractUser` : on garde tout ce que Django fournit (hachage des mots de passe,
  connexion, sessions) et on ajoute seulement le rôle. `AUTH_USER_MODEL = "accounts.User"` le déclare.
- `TextChoices` crée une énumération : la base stocke `"GESTIONNAIRE"`, l'écran affiche
  « Gestionnaire » via `get_role_display()`.
- Les propriétés `is_admin`, `is_staff_member`… rendent le code lisible : `if user.is_staff_member:`.

**Lien conducteur ↔ compte** : `Driver.user` est un `OneToOneField` : une fiche conducteur
correspond au plus à un compte. `on_delete=SET_NULL` : supprimer le compte ne supprime pas le conducteur.

## 3. Le contrôle d'accès

**Fichier** : `core/permissions.py`

```python
class RoleRequiredMixin(LoginRequiredMixin):
    allowed_roles = ()
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()        # → page de connexion
        if not user_has_role(request.user, self.allowed_roles):
            raise PermissionDenied(...)               # → erreur 403
        return super().dispatch(request, *args, **kwargs)

class StaffRequiredMixin(RoleRequiredMixin):
    allowed_roles = ("ADMIN", "GESTIONNAIRE")
```

- `dispatch` est la première méthode appelée par une vue basée sur une classe : on bloque **avant**
  tout traitement.
- Pour les vues sous forme de fonction, le décorateur `role_required(...)` fait la même chose.
- Masquer un menu dans le template ne suffit pas : quelqu'un pourrait taper l'URL. La vraie
  protection est côté serveur, et les tests (`accounts/tests.py`) le vérifient.

## 4. Les modèles et les contraintes d'intégrité

**Fichier** : `assignments/models.py`

```python
vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT, related_name="assignments")

constraints = [
    models.UniqueConstraint(fields=["vehicle"], condition=Q(status="EN_COURS"),
                            name="unique_active_assignment_per_vehicle"),
    models.CheckConstraint(condition=Q(return_mileage__isnull=True) |
                                     Q(return_mileage__gte=models.F("start_mileage")), ...),
]
```

- **`ForeignKey` + `PROTECT`** : un véhicule peut avoir plusieurs affectations (relation 1-N) et ne
  peut pas être supprimé tant qu'il en a. C'est ce qui **conserve l'historique**.
- **`related_name="assignments"`** permet d'écrire `vehicle.assignments.all()`.
- **`UniqueConstraint` avec `condition`** : un index unique *partiel*. Plusieurs affectations
  terminées pour un même véhicule sont permises, mais une seule `EN_COURS`. La règle est garantie
  **par la base elle-même**.
- **`CheckConstraint`** : la base refuse un kilométrage de retour inférieur au départ.
- La méthode **`clean()`** du modèle refait ces contrôles avec des messages clairs en français,
  affichés sous les champs du formulaire.

On a donc trois niveaux de validation : le formulaire (`forms.py`), le modèle (`clean()`) et la base
(contraintes).

## 5. La logique métier dans les services

**Fichier** : `assignments/services.py`

```python
@transaction.atomic
def create_assignment(assignment):
    vehicle = Vehicle.objects.select_for_update().get(pk=assignment.vehicle_id)
    check_assignment_rules(vehicle, assignment.driver)
    assignment.full_clean()
    assignment.save()
    vehicle.status = Vehicle.Status.ASSIGNED
    vehicle.save(...)
```

- **Pourquoi un fichier `services.py` ?** La même règle sert à la vue, à la commande de démonstration
  et aux tests. Si elle était écrite dans la vue, il faudrait la recopier : c'est la séparation des
  responsabilités.
- **`@transaction.atomic`** : tout est enregistré, ou rien. Si la mise à jour du véhicule échoue,
  l'affectation n'est pas créée non plus.
- **`select_for_update()`** verrouille la ligne du véhicule pendant la transaction : deux gestionnaires
  qui cliquent en même temps ne peuvent pas affecter le même véhicule. Sous SQLite le verrou est global ;
  sous PostgreSQL il porte sur la ligne.

`close_assignment()` enregistre le retour puis appelle `vehicle.refresh_status()`
(`vehicles/models.py`), qui recalcule le statut : *en entretien* si un entretien est en cours,
*affecté* s'il reste une affectation, sinon *disponible*. Les statuts *immobilisé* et *hors service*
sont des décisions humaines : la méthode ne les modifie jamais.

## 6. Le moteur d'alertes (partie centrale du projet)

**Fichier** : `alerts/services.py`

Chaque règle est une fonction **génératrice** (`yield`) qui produit des « candidats » :

```python
def insurance_candidates(cfg):
    for insurance in ...:
        level = _deadline_level(insurance.days_remaining, cfg)   # ("j7", URGENT), ("expire", CRITICAL)…
        if not level:
            continue
        yield Candidate(f"insurance:{insurance.pk}:{suffix}", title, desc, C.INSURANCE, priority, {...})
```

Puis `generate_alerts()` :

```python
open_alerts = {a.dedup_key: a for a in Alert.objects.filter(is_resolved=False)}
for rule in RULES:
    for candidate in rule(cfg):
        seen_keys.add(candidate.key)
        if candidate.key in open_alerts:
            continue                          # déjà signalée → pas de doublon
        Alert.objects.create(...)
# les alertes dont la situation a disparu sont marquées « résolues »
```

Points à savoir expliquer :
- **La clé de déduplication** (`insurance:12:j7`) décrit une situation précise. Tant qu'une alerte
  ouverte a cette clé, on n'en crée pas d'autre. Une contrainte SQL (`unique_open_alert`) le garantit aussi.
- **L'escalade** : quand l'assurance passe de 20 à 5 jours, la clé devient `insurance:12:j7` ;
  la nouvelle alerte (Urgent) est créée et l'ancienne (`…:j30`) est résolue automatiquement.
- **Ajouter une règle** = écrire une fonction de plus et l'ajouter à la liste `RULES`.
- **Exécution** : commande `generate_alerts` (`alerts/management/commands/`), bouton
  « Vérifier les échéances » et middleware `alerts/middleware.py`. `cache.add()` n'écrit que si la clé
  n'existe pas : la vérification tourne au plus une fois par période, même avec beaucoup de visiteurs.
- Les seuils (30 j, 7 j, 15 j, 1 000 km) se règlent dans **Paramètres** (`core/models.py`, `AppSettings`).

## 7. Les entretiens périodiques

**Fichier** : `maintenance/services.py`, fonction `get_due_schedules()`

1. On parcourt les entretiens terminés qui ont une prochaine date ou un prochain kilométrage, triés par date.
2. Le dictionnaire `latest[(vehicule, type)]` ne garde que **le plus récent** de chaque type et par véhicule.
   Faire une nouvelle vidange « efface » donc l'ancienne échéance.
3. On calcule `days_left` et `km_left` (prochain km − compteur actuel).
4. État `overdue` si l'un des deux est négatif, `soon` s'il passe sous le seuil.

`cost_by_vehicle()` utilise l'agrégation de l'ORM :

```python
.values("vehicle__registration_number").annotate(total=Sum("cost"), count=Count("id")).order_by("-total")
```

Cela produit **une seule requête SQL** `GROUP BY` au lieu d'une boucle Python sur tous les entretiens.

## 7 bis. Le module carburant

**Fichier** : `fuel/services.py`

- `FuelEntry.save()` calcule `total_amount = litres × prix` : le montant ne vient jamais du navigateur.
- `entries_with_consumption()` parcourt les pleins dans l'ordre du compteur et calcule, pour chaque plein complet,
  `litres / (km actuel − km précédent) × 100`. C'est la méthode « du plein à plein » : un plein complet remplace
  exactement ce qui a été consommé depuis le plein précédent.
- La moyenne d'un véhicule = total des litres mesurés ÷ total des km mesurés × 100 (et non la moyenne des
  moyennes, qui donnerait trop de poids aux petits trajets).
- `detect_anomalies()` compare le dernier plein à la moyenne des précédents ; au-delà de +30 %, la règle
  `fuel_candidates` du moteur d'alertes crée une alerte. Ajouter cette règle n'a demandé qu'une fonction de plus
  dans `RULES` : c'est l'intérêt de l'architecture du moteur.
- Le conducteur déclare un plein via `driver_fuel_declare` : le formulaire ne contient pas le champ véhicule,
  qui est imposé par le serveur (son affectation en cours). Même s'il envoie un autre véhicule, il est ignoré
  (vérifié par un test).

## 7 ter. Le journal d'audit

**Fichiers** : `audit/context.py`, `audit/middleware.py`, `audit/signals.py`, `audit/models.py`

Problème : les **signaux** Django (`pre_save`, `post_save`, `post_delete`) se déclenchent à chaque
enregistrement, mais ils ne reçoivent pas la requête HTTP, donc ne savent pas *qui* agit.

Solution en trois pièces :
1. `CurrentUserMiddleware` place l'utilisateur et son IP dans une **ContextVar** au début de chaque requête
   (une variable propre à chaque requête, même si le serveur en traite plusieurs à la fois).
2. `before_save` (pre_save) relit l'élément en base et en fait une « photo » lisible (`snapshot`) :
   libellés français, valeurs affichées comme à l'écran (« Immobilisé » plutôt que `IMMOBILISE`).
3. `after_save` (post_save) refait une photo, compare les deux et n'enregistre **que les champs modifiés**
   sous la forme `{"Statut": ["Disponible", "Immobilisé"]}` (champ JSON).

Avantage : aucune vue n'a été modifiée. Tout enregistrement passant par `save()` est tracé
automatiquement, y compris les changements de statut faits par les services métier.

Garanties :
- `AuditLog.save()` refuse toute modification d'une entrée existante (journal en ajout seul) ;
  l'interface d'administration Django est en lecture seule.
- Le nom d'utilisateur est copié : l'entrée reste lisible si le compte est supprimé.
- `password`, `last_login`… sont exclus (`EXCLUDED_FIELDS`).
- `audit_disabled()` suspend la journalisation (utilisé par `seed_demo`).
- Limite connue : `QuerySet.update()` ne déclenche pas les signaux. Les modifications métier passent donc par `save()`.

L'étiquette `{% audit_history object %}` (`audit/templatetags/audit_tags.py`) affiche l'historique sur
n'importe quelle fiche : c'est une *inclusion tag*, réutilisée sur cinq pages sans dupliquer de HTML.

## 8. Les formulaires

- `core/forms.py` → `BootstrapFormMixin` ajoute les classes CSS Bootstrap à tous les champs (pas de
  répétition dans chaque formulaire) et remplace les dates par un sélecteur HTML5.
- Les méthodes `clean_<champ>()` valident un champ (ex. `clean_mileage` : le compteur ne peut pas baisser),
  `clean()` valide plusieurs champs ensemble (ex. assurance : pas de chevauchement de périodes).
- `AssignmentCreateForm` ne propose que les véhicules disponibles et les conducteurs libres, **mais**
  revérifie quand même les règles dans `clean()`, car une requête peut être forgée à la main.

## 9. Les vues génériques et les mixins

`core/views_mixins.py` regroupe le comportement commun :
- `FilteredListMixin` : recherche `?q=` sur plusieurs champs avec des objets `Q` combinés par `|` (OU),
  filtres simples et pagination (`paginate_by = 10`).
- `SafeDeleteView` : suppression uniquement en POST ; intercepte `ProtectedError` pour afficher
  « Suppression impossible : historique lié » au lieu d'une erreur 500.
- `FormMessagesMixin` : messages de succès ou d'erreur (framework `messages` de Django).

Ainsi `VehicleListView` ne fait que quelques lignes : elle **compose** ces mixins (héritage multiple).

## 10. Tableau de bord et graphiques

- `dashboard/services.py` calcule les chiffres avec l'ORM (`Count`, `annotate`). Aucune valeur n'est
  écrite en dur.
- La vue passe les données au template, qui les sérialise avec `{{ charts|json_script:"dashboard-data" }}`.
  C'est la méthode sûre recommandée par Django (échappement automatique, pas d'injection de script).
- `static/js/charts.js` lit ce JSON et crée les graphiques Chart.js.

## 11. Rapports PDF et Excel sans duplication

- `reports/services.py` : chaque rapport est une fonction qui renvoie des `Section`
  (titre, colonnes, lignes, total). Le dictionnaire `REPORTS` est un **registre** :
  ajouter un rapport, c'est ajouter une fonction et une ligne.
- `reports/exporters.py` sait transformer **n'importe quelle** liste de sections en PDF (ReportLab :
  `SimpleDocTemplate`, `Table`, en-tête et pied dessinés par `decorate`) ou en Excel (OpenPyXL : une
  feuille par section, en-têtes stylés, format `#,##0" FCFA"`).
- La même vue `report_view` affiche l'aperçu HTML ou renvoie le fichier selon `?format=pdf|xlsx`.

## 12. Sécurité des fichiers

- `core/validators.py` vérifie l'extension, la taille et, pour les PDF, la signature `%PDF-`.
  `ImageField` vérifie avec Pillow que l'image est réelle.
- `core/views.py` → `protected_media` : les fichiers ne sont servis qu'aux utilisateurs connectés
  (`@login_required`).

## 13. Les tests

Chaque application a un `tests.py`. Les objets de test sont fabriqués par `core/testing.py`
(`make_vehicle()`, `make_driver()`…) pour éviter la répétition. Django crée une base temporaire
pour les tests puis la détruit : vos données ne sont pas touchées.

Exemple de test d'une règle de gestion :

```python
def test_vehicle_cannot_have_two_active_assignments(self):
    create_assignment(new_assignment(self.vehicle, self.driver))
    with self.assertRaises(ValidationError):
        create_assignment(new_assignment(self.vehicle, make_driver()))
```

Pendant le développement, ces tests ont révélé de vrais bugs, corrigés depuis (statut du véhicule lu
dans une copie périmée en mémoire, calcul des 12 derniers mois qui oubliait le mois en cours) :
c'est un bon exemple à raconter en soutenance.

## 13 bis. Les fonctionnalités de la version 3

### Statut « lu » propre à chaque utilisateur (`alerts/models.py`)

Au départ, `Alert.is_read` était un simple booléen : quand le gestionnaire lisait une alerte, elle
devenait lue pour tout le monde. On a remplacé ce champ par une **table d'association** `AlertRead`
(alerte, utilisateur, date) : une relation *plusieurs-à-plusieurs* entre alertes et utilisateurs.

```python
def with_read_state(self, user):
    return self.annotate(is_read=Exists(AlertRead.objects.filter(alert=OuterRef("pk"), user=user)))
```

`Exists` + `OuterRef` ajoutent l'attribut `is_read` **calculé par la base** pour l'utilisateur connecté
(une sous-requête SQL `EXISTS`). Les templates n'ont presque pas changé, car ils lisent toujours
`alerte.is_read`. La migration `0005` contient une étape `RunPython` qui recopie les lectures existantes
avant de supprimer l'ancien champ : on n'a perdu aucune donnée.

### Sinistres (`claims/services.py`)

`save_claim()` retrouve automatiquement l'affectation en cours et la police d'assurance valide **à la
date du sinistre** (pas aujourd'hui). La requête combine deux conditions avec `Q(...) | Q(...)` : affectation
encore en cours, ou retour postérieur à la date du sinistre. Le *reste à charge* est une propriété
calculée (`net_cost`) : il n'est pas stocké, il ne peut donc jamais être incohérent.

### Coût de revient (`vehicles/costs.py`)

Chaque poste est une agrégation `Sum` en base. Le coût au km utilise le champ `acquisition_mileage`, sans
lequel on diviserait par des kilomètres parcourus avant l'achat. Le seuil « à étudier » (30 % du prix
d'achat par an) est une constante nommée `REVIEW_RATIO` : facile à justifier et à modifier.

### Planning (`assignments/planning.py` + `templates/assignments/planning.html`)

Aucune bibliothèque de calendrier : une **grille CSS** (`display: grid`) avec une colonne par jour.
Le service transforme chaque affectation en « segment » (`col` = colonne de début, `span` = nombre de jours),
coupé aux bornes du mois par `_segment()`. Le template place la barre avec
`grid-column: {{ col }} / span {{ span }}`. Un retard est prolongé jusqu'à aujourd'hui et coloré en rouge.

### Notifications email (`alerts/notifications.py`)

- Destinataires : administrateurs et gestionnaires actifs, avec email, et qui l'acceptent (`email_alerts`).
- Alertes envoyées : urgentes et critiques, jamais envoyées (`emailed_at` vide), puis datées. Un renvoi est impossible.
- `EmailMultiAlternatives` envoie une version texte **et** HTML ; un email par destinataire pour ne pas
  dévoiler les adresses des autres.
- Le moyen d'envoi est choisi dans `settings.py` : console par défaut, SMTP si `EMAIL_HOST` est défini.
  Pendant les tests, Django utilise automatiquement une boîte mémoire (`mail.outbox`), ce qui permet de vérifier
  les emails sans rien envoyer.

### Import Excel (`vehicles/importer.py`)

Point clé à défendre : **chaque ligne est validée par le même `VehicleForm` que la saisie manuelle**. Les règles
(immatriculation unique, kilométrage, dates…) ne sont donc écrites qu'une fois. Les libellés Excel
(« Pick-up ») sont convertis en codes (`PICKUP`), et les doublons *à l'intérieur du fichier* sont aussi détectés.
`import_rows()` est décoré par `@transaction.atomic` et n'est appelé que s'il n'y a aucune erreur : c'est
l'import « tout ou rien ».

### Mise en production (`config/settings.py`, `.env.example`, `DEPLOIEMENT.md`)

- `load_env_file()` lit un fichier `.env` (sans bibliothèque externe) ; les secrets ne sont jamais dans le code
  ni sur GitHub (`.gitignore`).
- Si `DEBUG` est désactivé sans clé secrète, l'application **refuse de démarrer** (`ImproperlyConfigured`) plutôt
  que de tourner avec une clé connue de tous.
- `python manage.py check --deploy` vérifie la configuration de sécurité.

## 14. Questions probables et éléments de réponse

| Question | Réponse courte |
|---|---|
| Pourquoi Django ? | ORM, authentification, protection CSRF, formulaires et admin intégrés : moins de code de sécurité à écrire soi-même. |
| Comment empêchez-vous deux affectations simultanées ? | Trois niveaux : formulaire, service (avec verrou `select_for_update`) et index unique conditionnel en base. |
| Que se passe-t-il si on supprime un véhicule ? | Refusé s'il a un historique (`PROTECT`) ; on le passe « Hors service ». |
| Comment évitez-vous les alertes en double ? | Clé de déduplication unique parmi les alertes ouvertes. |
| Les mots de passe sont-ils stockés en clair ? | Non, hachés en PBKDF2 avec sel par `create_user` / `set_password`. |
| Comment passer à PostgreSQL ? | Changer les variables d'environnement `DB_*` et relancer `migrate` ; le code ne change pas grâce à l'ORM. |
| Comment savez-vous qui a modifié une fiche ? | Journal d'audit alimenté par les signaux Django ; l'utilisateur vient d'un middleware (ContextVar). |
| Pourquoi une table AlertRead plutôt qu'un booléen ? | Le statut « lu » dépend de l'utilisateur : c'est une relation plusieurs-à-plusieurs entre alertes et utilisateurs. |
| Comment éviter qu'un import Excel corrompe la base ? | Validation de chaque ligne par le formulaire de saisie, puis enregistrement dans une transaction, seulement si tout est valide. |
| Comment ne pas envoyer deux fois le même email ? | Le champ `emailed_at` marque les alertes déjà envoyées. |
| Comment calculez-vous la consommation ? | Méthode du plein à plein : litres d'un plein complet ÷ km depuis le plein précédent × 100. |
| Un conducteur peut-il voir les données des autres ? | Non : il n'a accès qu'à `driver_space`, filtré sur `request.user.driver_profile`, et reçoit 403 ailleurs. |

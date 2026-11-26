# Guide de FLEET MANAGER

**But, fonctionnement et points à connaître**

Ce guide explique *ce que fait* l'application et *comment s'en servir*. Les autres documents :

| Document | Contenu |
|---|---|
| `README.md` | Installation, commandes, base de données, règles de gestion |
| `DOCUMENTATION_CODE.md` | Explication du code Python, pour la soutenance |
| `DEPLOIEMENT.md` | Mise en ligne sur PythonAnywhere |
| **Ce guide** | Le but de l'application, son fonctionnement concret, les points à connaître |

---

## 1. À quoi sert FLEET MANAGER ?

### Le problème
Une entreprise, une administration ou une ONG qui possède des véhicules doit suivre beaucoup de choses :
qui conduit quel véhicule, quand faire la vidange, quand renouveler l'assurance, le permis de chaque conducteur,
la vignette, le carburant consommé, les accidents… Souvent, ces informations sont dispersées dans des cahiers
et des fichiers Excel. Résultat : **on oublie des échéances** (un véhicule roule sans assurance, un permis expire)
et **on ne connaît pas le coût réel** de chaque véhicule.

### La solution
FLEET MANAGER **centralise tout dans une seule application web** et :
1. **surveille les échéances à votre place**, en générant des **alertes automatiques** ;
2. **applique les règles de gestion** : impossible, par exemple, d'affecter un véhicule non assuré ou déjà en mission ;
3. **calcule les indicateurs** utiles pour décider : dépenses, consommation, coût au kilomètre, véhicules à remplacer ;
4. **garde l'historique** de tout ce qui s'est passé, et de qui l'a fait.

### Pour qui ?
Trois profils d'utilisateurs, chacun avec des droits différents :

| Profil | Ce qu'il fait | Compte de démo |
|---|---|---|
| **Administrateur** | Tout, plus la gestion des comptes, les paramètres et le journal d'audit | `admin` / `Admin@2026` |
| **Gestionnaire** | Gère le parc au quotidien : véhicules, conducteurs, affectations, entretiens, assurances, carburant, sinistres, alertes, rapports | `gestionnaire` / `Gestion@2026` |
| **Conducteur** | Consulte son profil, le véhicule qui lui est confié et son historique ; déclare ses pleins | `conducteur` / `Conducteur@2026` |

---

## 2. Comment ça marche : la vie d'un véhicule

Le plus simple pour comprendre l'application est de suivre un véhicule du début à la fin.

```
 Achat ──► Fiche véhicule ──► Assurance ──► Affectation à un conducteur ──► Retour
             │                                   │                           │
             │                       pleins de carburant             km mis à jour
             ▼                                   │                           ▼
       Entretiens réguliers ◄──── alertes ───────┴────────────────► Disponible à nouveau
             │
       Sinistre éventuel ──► Immobilisation ──► Réparation ──► Remise en service
             │
       Fin de vie ──► « Hors service » (l'historique est conservé)
```

### Étape 1 : enregistrer le véhicule
**Véhicules → Ajouter un véhicule** : immatriculation (unique), marque, modèle, catégorie, carburant, année,
numéro de châssis, prix et date d'achat, kilométrage, carte grise, échéance de la vignette, service…
Pour un parc existant, **Véhicules → Importer** permet de tout charger depuis un fichier Excel (un modèle est fourni).

### Étape 2 : l'assurer
**Assurances → Ajouter une assurance** : compagnie, numéro de police, type, dates, prime.
⚠️ **Sans assurance valide, le véhicule ne peut pas être affecté.**

### Étape 3 : enregistrer les conducteurs
**Conducteurs → Ajouter un conducteur** : identité, permis (numéro, catégorie, dates), matricule, contact d'urgence…
L'administrateur peut ensuite lui créer un **compte « Conducteur »** (menu Utilisateurs) relié à sa fiche.

### Étape 4 : affecter le véhicule (départ en mission)
**Affectations → Nouvelle affectation** : on choisit le véhicule, le conducteur, les dates, le kilométrage au départ,
le niveau de carburant, le motif et la destination.
- La liste ne propose **que les véhicules disponibles et assurés**, et **que les conducteurs actifs, au permis valide et sans véhicule**.
- Le véhicule passe automatiquement au statut **« Affecté »**.

### Étape 5 : le retour
Sur l'affectation, cliquez sur **Enregistrer le retour** : date, kilométrage, carburant, état du véhicule.
- Le compteur du véhicule est mis à jour et le véhicule redevient **« Disponible »**.
- Si des **dommages** sont signalés, l'application propose de **déclarer un sinistre**.

### Étape 6 : l'entretien
**Entretiens → Enregistrer un entretien** : type (vidange, freins, contrôle technique…), garage, coût, facture.
- En renseignant la **date ou le kilométrage du prochain entretien**, l'application vous préviendra à temps.
- Un entretien **« En cours »** met le véhicule au statut **« En entretien »** : il ne peut plus être affecté.
- La page **À prévoir** liste les véhicules dont l'entretien approche ou est dépassé.

### Étape 7 : le carburant
**Carburant → Enregistrer un plein** (ou, pour le conducteur, **Déclarer un plein** depuis son espace).
Le montant est calculé automatiquement, et la page **Consommation** donne les **litres aux 100 km** de chaque véhicule.

### Étape 8 : en cas d'accident, de vol ou de panne grave
**Sinistres → Déclarer un sinistre** : type, lieu, circonstances, photos, constat.
- L'application retrouve **seule** le conducteur et l'assurance valides à la date du sinistre.
- Une case permet d'**immobiliser** le véhicule immédiatement.
- On suit ensuite le dossier avec l'assureur (déclaré, en expertise, indemnisé…) et le **reste à charge**.

### Étape 9 : fin de vie
On ne supprime pas un véhicule qui a un historique (l'application le refuse) : on le passe **« Hors service »**.
Il disparaît des listes de choix, mais toutes ses données restent consultables.

---

## 3. Les statuts d'un véhicule

| Statut | Qui le met ? | Peut être affecté ? |
|---|---|---|
| **Disponible** | Automatique (ou manuel) | ✅ Oui, s'il est assuré |
| **Affecté** | Automatique, à l'affectation | ❌ Déjà en mission |
| **En entretien** | Automatique, entretien « En cours » | ❌ |
| **Immobilisé** | Manuel (panne, sinistre…) | ❌ |
| **Hors service** | Manuel (réforme) | ❌ |

« Affecté » et « En entretien » se gèrent **tout seuls**. Les autres se choisissent sur la fiche du véhicule.

---

## 4. Les alertes : le cœur de l'application

### Ce qui est surveillé
| Situation | Quand ? | Priorité |
|---|---|---|
| Assurance, permis, vignette | 30 jours avant / 7 jours avant / dépassé | Attention / Urgent / Critique |
| Entretien périodique | 15 jours ou 1 000 km avant / dépassé | Information / Urgent |
| Contrôle technique | 30 jours avant / dépassé | Attention / Critique |
| Véhicule immobilisé | Dès qu'il l'est | Attention |
| Retour d'affectation en retard | Dès le lendemain de la date prévue | Attention (Urgent après 3 jours) |
| Consommation de carburant anormale | Dernier plein > moyenne + 30 % | Attention |
| Sinistre non déclaré à l'assureur | Après 5 jours | Urgent |
| Sinistre qui traîne | Ouvert depuis plus de 30 jours | Attention |

Les seuils (30 j, 7 j, 15 j, 1 000 km…) se règlent dans **Paramètres** (administrateur).

### Comment elles fonctionnent
- **Automatiques** : la vérification se lance toute seule pendant la navigation (au plus toutes les 10 minutes),
  avec le bouton **Vérifier les échéances**, ou chaque jour par la commande `python manage.py generate_alerts`.
- **Jamais en double** : une même situation ne crée qu'une seule alerte, même si on relance la vérification 100 fois.
- **Résolution automatique** : quand le problème disparaît (assurance renouvelée, véhicule réparé), l'alerte se
  ferme d'elle-même et part dans l'historique (filtre « Historique (résolues) »).
- **Lu / non lu par personne** : si le gestionnaire lit une alerte, elle reste « non lue » pour l'administrateur.
- **Où les voir** : la cloche 🔔 en haut (avec le nombre d'alertes non lues), la page **Alertes**, la fiche du
  véhicule ou du conducteur concerné, et les « Alertes urgentes » du tableau de bord.
- **Par email** : les nouvelles alertes urgentes et critiques sont envoyées aux administrateurs et gestionnaires
  qui l'acceptent (option dans **Mon profil**). Sans configuration, les emails s'affichent dans le terminal.

---

## 5. Tour des écrans

| Menu | Ce qu'on y trouve |
|---|---|
| **Tableau de bord** | 10 indicateurs cliquables, 5 graphiques, alertes urgentes, prochaines échéances, dernières affectations et entretiens |
| **Alertes** | Toutes les alertes, filtrables par priorité, catégorie, lu / non lu ; historique des alertes résolues |
| **Véhicules** | Liste filtrable, fiche complète (historique, entretiens, carburant, sinistres, coût de revient), import Excel, page *Coût de revient* |
| **Conducteurs** | Liste, filtre des permis expirés ou bientôt expirés, fiche avec historique |
| **Affectations** | Missions en cours, terminées, en retard ; enregistrement des retours |
| **Planning** | Vue mensuelle : une ligne par véhicule, une barre par mission ou entretien |
| **Entretiens** | Historique, *À prévoir* (échéances), *Dépenses* (par véhicule, par type, par mois) |
| **Assurances** | Polices valides, qui expirent bientôt, expirées ; liste des véhicules non assurés |
| **Carburant** | Pleins et page *Consommation* (L/100 km, dépenses, anomalies) |
| **Sinistres** | Déclarations, suivi assureur, coûts et reste à charge |
| **Rapports** | 12 rapports, filtrables par période, exportables en **PDF** et **Excel** |
| **Utilisateurs** *(admin)* | Création des comptes, rôles, lien avec une fiche conducteur, réinitialisation des mots de passe |
| **Journal d'audit** *(admin)* | Qui a créé, modifié ou supprimé quoi, quand, depuis quelle adresse IP, avec le détail « avant / après » |
| **Paramètres** | Nom de l'organisation, seuils des alertes, configuration des emails |
| **Recherche** (barre du haut) | Recherche d'un véhicule, conducteur, affectation ou assurance |

Le **conducteur** n'a que **Mon véhicule** (son espace), **Mon profil** et **Paramètres**.

---

## 6. Les règles que l'application fait respecter

Ces règles sont vérifiées **par le serveur**, pas seulement à l'écran : on ne peut pas les contourner.

**Affectations**
- Un véhicule ne peut avoir **qu'une seule** affectation en cours, et un conducteur **qu'un seul** véhicule.
- Le véhicule doit être **disponible** et **assuré** ; le conducteur **actif** avec un **permis valide**.
- Les kilométrages ne peuvent jamais diminuer.
- Une affectation terminée ou annulée **ne se modifie plus** : elle fait partie de l'historique.

**Véhicules**
- Immatriculation et numéro de châssis **uniques**.
- Un véhicule en mission ne peut pas être mis « Disponible » ni « Hors service » avant son retour
  (« Immobilisé » reste possible, pour une panne en route).
- Un entretien ne peut pas démarrer tant que le véhicule est en mission.

**Données et historique**
- Un véhicule ou un conducteur qui a un historique **ne peut pas être supprimé**.
- Deux assurances d'un même véhicule ne peuvent pas se chevaucher.
- Les montants (plein, reste à charge) sont **calculés par le serveur**.

**Sécurité**
- Chaque page vérifie le rôle de l'utilisateur (sinon : « Accès refusé »).
- Les mots de passe sont **chiffrés** (hachés) : personne ne peut les lire, même l'administrateur.
- Les factures, attestations et constats ne sont visibles que par les administrateurs et gestionnaires.
- Toute suppression demande une **confirmation**.

---

## 7. Comment c'est construit (version simple)

```
   Navigateur (pages HTML, Bootstrap, graphiques Chart.js)
        │  ▲
        ▼  │  requêtes / pages
   Django (Python)
     ├── vues        : reçoivent la demande, vérifient les droits
     ├── formulaires : contrôlent les saisies
     ├── services    : appliquent les règles de gestion (affecter, clôturer, alerter…)
     └── ORM         : traduit le Python en requêtes SQL
        │
        ▼
   Base de données SQLite (fichier db.sqlite3)
```

- **Langage** : Python 3, avec le framework **Django 5.2**.
- **Base de données** : **SQLite**, un simple fichier `db.sqlite3` à la racine du projet. Elle peut être remplacée par
  **PostgreSQL** sans changer le code.
- **13 applications Django**, une par domaine : comptes, véhicules, conducteurs, affectations, entretiens,
  assurances, carburant, sinistres, alertes, journal d'audit, tableau de bord, rapports, noyau commun.
- **PDF** avec ReportLab, **Excel** avec OpenPyXL, images avec Pillow.
- **115 tests automatisés** vérifient le fonctionnement (`python manage.py test`).

Pour le détail du code : `DOCUMENTATION_CODE.md`.

---

## 8. Ce qu'il faut savoir au quotidien

### Démarrer l'application
```bat
python manage.py runserver
```
puis ouvrir http://127.0.0.1:8000. Ou bien double-cliquer sur `lancer.bat`.

### Les commandes utiles
| Commande | À quoi elle sert |
|---|---|
| `python manage.py runserver` | Démarrer l'application |
| `python manage.py migrate` | Mettre la base à jour (**après chaque `git pull`**) |
| `python manage.py seed_demo --reset` | Recharger des données de démonstration fraîches |
| `python manage.py generate_alerts` | Vérifier les échéances et envoyer les emails |
| `python manage.py test` | Lancer les 115 tests |
| `python manage.py createsuperuser` | Créer un nouvel administrateur |

### Les données de démonstration
`seed_demo` crée 15 véhicules, 10 conducteurs, des affectations (en cours et terminées), 77 entretiens,
30 assurances, 72 pleins, 3 sinistres et une vingtaine d'alertes. Toutes les personnes sont **fictives**.
Les dates sont calculées **par rapport au jour du lancement** : les alertes sont donc toujours réalistes.
Quelques situations à montrer :
- **11 EG 5527** : immobilisé, assurance expirée, sinistre non déclaré ;
- **11 HM 7712** : disponible mais **assurance expirée**, donc absent de « Nouvelle affectation » ;
- **11 DF 4410** : en atelier (entretien en cours) ;
- **11 VW 6050** : hors service ;
- **11 JK 4521** : confié au conducteur de démo (KABORÉ Issouf), avec une consommation anormale ;
- **NIKIÉMA Clarisse** : permis expiré, donc impossible de lui affecter un véhicule.

⚠️ `seed_demo --reset` **efface** les données du parc pour les remplacer : ne l'utilisez pas sur de vraies données.

### Où sont les choses
| Quoi | Où |
|---|---|
| Base de données | `db.sqlite3` (à la racine, **pas** sur GitHub) |
| Photos et documents téléversés | dossier `media/` (**pas** sur GitHub) |
| Réglages techniques | `config/settings.py` et le fichier `.env` (secrets, jamais sur GitHub) |
| Code source | https://github.com/fabbxss0/fleet_manager |
| Administration technique Django | http://127.0.0.1:8000/admin |

### Problèmes fréquents
| Symptôme | Solution |
|---|---|
| « You have N unapplied migration(s) » ou « no such column » | `python manage.py migrate` |
| « Accès refusé » | Votre rôle n'autorise pas cette page : c'est voulu |
| Un véhicule n'apparaît pas dans « Nouvelle affectation » | Il n'est pas disponible ou **pas assuré** aujourd'hui |
| Un conducteur n'apparaît pas | Il est inactif, son permis est expiré, ou il a déjà un véhicule |
| « Suppression impossible » | L'élément a un historique : passez-le « Hors service » / « Inactif » |
| Les emails ne partent pas | Normal sans configuration : ils s'affichent dans le terminal (voir le README) |
| Plus de données cohérentes | `python manage.py seed_demo --reset` |

### Limites actuelles (à dire honnêtement en soutenance)
- Pas de réinitialisation du mot de passe par email : c'est l'administrateur qui le fait.
- Pas de limite au nombre de tentatives de connexion.
- Pas de géolocalisation des véhicules ni d'application mobile (ce sont des perspectives).
- SQLite convient à un usage modéré ; pour beaucoup d'utilisateurs simultanés, passer à PostgreSQL.

---

## 9. Démonstration conseillée (≈ 10 minutes)

1. `python manage.py seed_demo --reset`, puis lancer le serveur.
2. **Connexion `admin`** → **Tableau de bord** : présenter les indicateurs et les graphiques.
3. **Alertes** : montrer les priorités, ouvrir une alerte critique (elle mène à l'élément concerné).
4. **Nouvelle affectation** : montrer que **11 HM 7712** (disponible mais assurance expirée) et **NIKIÉMA Clarisse**
   (permis expiré) ne sont pas proposés, puis affecter un véhicule disponible.
5. **Enregistrer le retour** avec un kilométrage inférieur au départ → **refusé** ; puis un retour correct avec
   « Dommages légers » → proposition de sinistre.
6. **Planning** : la nouvelle mission apparaît.
7. **Rapports** → *Rapport général* → **Exporter en PDF** puis **Excel**.
8. **Journal d'audit** : toutes les actions qu'on vient de faire y figurent, avec le détail.
9. Se déconnecter, **connexion `conducteur`** : il ne voit que son véhicule ; tenter d'ouvrir `/vehicules/`
   dans l'adresse → **Accès refusé**.

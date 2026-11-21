# Mettre FLEET MANAGER en ligne sur PythonAnywhere (gratuit)

PythonAnywhere héberge gratuitement une application Django à l'adresse
`https://VOTRECOMPTE.pythonanywhere.com`. Comptez une vingtaine de minutes.
Dans tout ce guide, remplacez **`VOTRECOMPTE`** par votre nom d'utilisateur PythonAnywhere.

> Le dépôt GitHub doit être accessible depuis PythonAnywhere. S'il est **privé**, utilisez un
> jeton d'accès GitHub (Settings → Developer settings → Personal access tokens) à la place du
> mot de passe lors du `git clone`, ou rendez le dépôt public le temps du clonage.

---

## 1. Créer le compte

1. Inscrivez-vous sur <https://www.pythonanywhere.com> (offre **Beginner**, gratuite).
2. Ouvrez l'onglet **Consoles** → **Bash**.

## 2. Récupérer le code et installer les dépendances

Dans la console Bash de PythonAnywhere :

```bash
git clone https://github.com/fabbxss0/fleet_manager.git
```

```bash
cd fleet_manager
```

```bash
mkvirtualenv --python=python3.12 fleet
```

```bash
pip install -r requirements.txt
```

(`mkvirtualenv` crée l'environnement virtuel `fleet` et l'active. Plus tard, pour le réactiver : `workon fleet`.)

## 3. Configurer les paramètres de production

```bash
cp .env.example .env
```

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

Copiez la clé affichée, puis ouvrez le fichier `.env` (onglet **Files** → `fleet_manager/.env`) et réglez :

```
DJANGO_DEBUG=0
DJANGO_SECRET_KEY=la-clé-copiée
DJANGO_ALLOWED_HOSTS=VOTRECOMPTE.pythonanywhere.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://VOTRECOMPTE.pythonanywhere.com
SITE_URL=https://VOTRECOMPTE.pythonanywhere.com
```

Le fichier `.env` reste sur le serveur : il n'est jamais envoyé sur GitHub.

## 4. Créer la base et les fichiers statiques

```bash
python manage.py migrate
```

```bash
python manage.py collectstatic --noinput
```

```bash
python manage.py seed_demo
```

La dernière commande charge les données de démonstration. Pour un vrai usage, remplacez-la par
`python manage.py createsuperuser`.

## 5. Créer l'application web

Onglet **Web** → **Add a new web app** → **Next** → **Manual configuration** (surtout pas « Django ») → **Python 3.12** → **Next**.

Sur la page de l'application :

| Rubrique | Valeur |
|---|---|
| **Virtualenv** | `/home/VOTRECOMPTE/.virtualenvs/fleet` |
| **Source code** | `/home/VOTRECOMPTE/fleet_manager` |
| **Static files** → URL `/static/` | `/home/VOTRECOMPTE/fleet_manager/staticfiles` |

Ne déclarez **pas** `/media/` dans « Static files » : les photos et justificatifs doivent rester
réservés aux utilisateurs connectés, et l'application s'en charge elle-même.

Cliquez sur le lien du **WSGI configuration file**, effacez tout son contenu et remplacez-le par :

```python
import os
import sys

path = "/home/VOTRECOMPTE/fleet_manager"
if path not in sys.path:
    sys.path.insert(0, path)

os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"

from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()
```

Enregistrez, puis activez **Force HTTPS** (rubrique *Security*) et cliquez sur le bouton vert **Reload**.

Ouvrez `https://VOTRECOMPTE.pythonanywhere.com` et connectez-vous avec `admin` / `Admin@2026`.
**Changez ensuite les mots de passe de démonstration** (menu Utilisateurs) : le site est public.

## 6. Générer les alertes chaque jour

Onglet **Tasks** → *Scheduled tasks* → heure `06:00` (UTC, soit 06:00 à Ouagadougou), commande :

```bash
/home/VOTRECOMPTE/.virtualenvs/fleet/bin/python /home/VOTRECOMPTE/fleet_manager/manage.py generate_alerts
```

Le compte gratuit autorise une tâche quotidienne, ce qui suffit. Les alertes se mettent aussi à jour
pendant la navigation.

## 7. Emails (facultatif)

Avec Gmail, qui fonctionne sur les comptes gratuits PythonAnywhere :
1. Activez la validation en deux étapes sur votre compte Google.
2. Créez un **mot de passe d'application** : Compte Google → Sécurité → Mots de passe des applications.
3. Ajoutez dans `.env` :

```
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=1
EMAIL_HOST_USER=votre.adresse@gmail.com
EMAIL_HOST_PASSWORD=le-mot-de-passe-d-application
DEFAULT_FROM_EMAIL=FLEET MANAGER <votre.adresse@gmail.com>
```

4. **Reload** dans l'onglet Web, puis *Paramètres → M'envoyer un email de test* dans l'application.

## 8. Mettre à jour le site après une modification

```bash
cd ~/fleet_manager && workon fleet
```

```bash
git pull
```

```bash
pip install -r requirements.txt && python manage.py migrate && python manage.py collectstatic --noinput
```

Puis **Reload** dans l'onglet Web.

## En cas de problème

| Symptôme | Solution |
|---|---|
| « Something went wrong » | Onglet Web → **Error log** : la dernière ligne indique la cause |
| `DisallowedHost` | `DJANGO_ALLOWED_HOSTS` ne correspond pas exactement à l'adresse du site |
| Erreur CSRF à la connexion | Vérifier `DJANGO_CSRF_TRUSTED_ORIGINS` (avec `https://`) |
| Page sans mise en forme | Vérifier le chemin `/static/` → `staticfiles` et relancer `collectstatic` |
| `ImproperlyConfigured … DJANGO_SECRET_KEY` | Le fichier `.env` est absent ou la clé n'est pas renseignée |
| `no such table` | `python manage.py migrate` n'a pas été lancé |
| Le compte gratuit s'arrête | Bouton **Run until 3 months from today** dans l'onglet Web, à cliquer une fois tous les 3 mois |

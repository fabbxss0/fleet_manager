@echo off
REM Lancement de FLEET MANAGER sous Windows (a executer dans le dossier du projet).
REM Utilise l environnement .venv (PyCharm) ou venv s il existe, sinon le cree.
cd /d "%~dp0"
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
) else if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else (
    echo Creation de l environnement virtuel .venv ...
    python -m venv .venv
    call .venv\Scripts\activate.bat
)
REM Dependances et base de donnees toujours a jour (sans effet si rien n a change)
pip install -q -r requirements.txt
python manage.py migrate
REM Donnees de demonstration seulement si la base est vide
python manage.py shell -c "from vehicles.models import Vehicle; import sys; sys.exit(0 if Vehicle.objects.exists() else 1)" || python manage.py seed_demo
python manage.py runserver

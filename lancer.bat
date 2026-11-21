@echo off
REM Lancement rapide de FLEET MANAGER sous Windows (a executer dans le dossier du projet)
if not exist venv (
    python -m venv venv
    call venv\Scripts\activate
    pip install -r requirements.txt
    python manage.py migrate
    python manage.py seed_demo
) else (
    call venv\Scripts\activate
)
python manage.py runserver

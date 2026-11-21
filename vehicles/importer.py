"""
Import de véhicules depuis un fichier Excel (.xlsx).

1. L'utilisateur télécharge un modèle (build_template) avec les bonnes colonnes,
   des listes déroulantes et une ligne d'exemple.
2. Chaque ligne du fichier rempli est validée avec le MÊME formulaire que la
   saisie manuelle (VehicleForm) : les règles ne sont écrites qu'une fois.
3. L'import est « tout ou rien » : s'il reste une seule erreur, rien n'est
   enregistré (transaction), et l'utilisateur voit la liste des erreurs par ligne.
"""
from datetime import date, datetime
from io import BytesIO

from django.db import transaction
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

from .forms import VehicleForm
from .models import Vehicle

MAX_ROWS = 500
MAX_SIZE = 2 * 1024 * 1024

# (en-tête affiché, champ du modèle, obligatoire, exemple)
COLUMNS = [
    ("Immatriculation", "registration_number", True, "11 AB 1234"),
    ("Marque", "brand", True, "Toyota"),
    ("Modèle", "model", True, "Hilux"),
    ("Catégorie", "category", True, "Pick-up"),
    ("Carburant", "fuel_type", True, "Diesel"),
    ("Couleur", "color", False, "Blanc"),
    ("Année", "year", True, 2022),
    ("N° de châssis", "chassis_number", True, "JTEBX3FJ10K123456"),
    ("Date d'acquisition (JJ/MM/AAAA)", "acquisition_date", True, "15/03/2023"),
    ("Prix d'acquisition (FCFA)", "acquisition_price", True, 24500000),
    ("Kilométrage actuel", "mileage", True, 45200),
    ("Kilométrage à l'acquisition", "acquisition_mileage", False, 0),
    ("Réservoir (L)", "tank_capacity", False, 80),
    ("Puissance fiscale (CV)", "fiscal_power", False, 12),
    ("N° de carte grise", "registration_card_number", False, "CG-2023-0001"),
    ("Mise en circulation (JJ/MM/AAAA)", "first_registration_date", False, "01/03/2023"),
    ("Échéance vignette (JJ/MM/AAAA)", "vignette_expiry_date", False, "31/12/2026"),
    ("Service", "department", False, "Logistique"),
    ("Places", "seats", False, 5),
    ("Boîte de vitesses", "transmission", False, "Manuelle"),
    ("Observations", "notes", False, ""),
]
CHOICE_FIELDS = {
    "category": Vehicle.Category.choices,
    "fuel_type": Vehicle.Fuel.choices,
    "transmission": Vehicle.Transmission.choices,
}
DATE_FIELDS = {"acquisition_date", "first_registration_date", "vignette_expiry_date"}


def build_template():
    """Fichier modèle à remplir, avec listes déroulantes et une feuille d'aide."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Véhicules"
    header_fill = PatternFill("solid", fgColor="0B1F3A")
    for col, (label, field, required, example) in enumerate(COLUMNS, start=1):
        cell = ws.cell(row=1, column=col, value=label + (" *" if required else ""))
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = header_fill
        ws.cell(row=2, column=col, value=example).font = Font(italic=True, color="64748B")
        ws.column_dimensions[cell.column_letter].width = max(len(label) + 4, 14)
        if field in CHOICE_FIELDS:
            options = ",".join(lbl for _, lbl in CHOICE_FIELDS[field])
            validation = DataValidation(type="list", formula1=f'"{options}"', allow_blank=not required)
            validation.error = "Choisissez une valeur de la liste."
            ws.add_data_validation(validation)
            validation.add(f"{cell.column_letter}2:{cell.column_letter}{MAX_ROWS + 1}")
    ws.freeze_panes = "A2"
    help_ws = wb.create_sheet("Aide")
    lines = [
        "Mode d'emploi de l'import",
        "1. Remplissez une ligne par véhicule dans la feuille « Véhicules » (la ligne 2 est un exemple : remplacez-la).",
        "2. Les colonnes marquées * sont obligatoires.",
        "3. Dates au format JJ/MM/AAAA. Montants et kilométrages en chiffres, sans espace ni « FCFA ».",
        "4. L'immatriculation et le numéro de châssis doivent être uniques.",
        "5. Dans FLEET MANAGER, cliquez d'abord sur « Vérifier le fichier » : rien n'est enregistré tant qu'il reste une erreur.",
        f"6. {MAX_ROWS} véhicules au maximum par fichier.",
        "",
        "Valeurs possibles :",
    ] + [f"- {field} : " + ", ".join(lbl for _, lbl in choices) for field, choices in
         (("Catégorie", Vehicle.Category.choices), ("Carburant", Vehicle.Fuel.choices),
          ("Boîte de vitesses", Vehicle.Transmission.choices))]
    for i, line in enumerate(lines, start=1):
        help_ws.cell(row=i, column=1, value=line).font = Font(bold=(i == 1), size=13 if i == 1 else 11)
    help_ws.column_dimensions["A"].width = 120
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def _convert(field, value):
    """Valeur Excel -> valeur attendue par le formulaire Django."""
    if value is None:
        return ""
    if field in DATE_FIELDS:
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        text = str(value).strip()
        try:
            return datetime.strptime(text, "%d/%m/%Y").date().isoformat()
        except ValueError:
            return text  # le formulaire signalera la date invalide
    if field in CHOICE_FIELDS:
        text = str(value).strip().lower()
        for code, label in CHOICE_FIELDS[field]:
            if text in (code.lower(), label.lower()):
                return code
        return str(value).strip()
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return str(value).strip() if isinstance(value, str) else value


def parse_workbook(uploaded_file):
    """Lit le fichier et valide chaque ligne. Retourne (lignes, erreur_générale)."""
    if not uploaded_file.name.lower().endswith(".xlsx"):
        return [], "Le fichier doit être au format Excel .xlsx (utilisez le modèle fourni)."
    if uploaded_file.size > MAX_SIZE:
        return [], "Le fichier dépasse 2 Mo."
    try:
        wb = load_workbook(uploaded_file, read_only=True, data_only=True)
    except Exception:
        return [], "Impossible de lire ce fichier Excel. Vérifiez qu'il n'est pas corrompu."
    ws = wb.worksheets[0]
    rows_iter = ws.iter_rows(values_only=True)
    header = [str(h or "").replace("*", "").strip() for h in next(rows_iter, [])]
    expected = [label for label, *_ in COLUMNS]
    missing = [label for label, _, required, _ in COLUMNS if required and label not in header]
    if missing:
        return [], "Colonnes obligatoires absentes : " + ", ".join(missing) + ". Utilisez le modèle fourni."
    index = {label: header.index(label) for label in expected if label in header}

    results, seen = [], {}
    for line_number, values in enumerate(rows_iter, start=2):
        if not values or all(v in (None, "") for v in values):
            continue
        if len(results) >= MAX_ROWS:
            return [], f"Le fichier contient plus de {MAX_ROWS} véhicules."
        data = {"status": Vehicle.Status.AVAILABLE}
        for label, field, _, _ in COLUMNS:
            if label in index and index[label] < len(values):
                data[field] = _convert(field, values[index[label]])
        form = VehicleForm(data=data)
        errors = []
        if not form.is_valid():
            for field, messages in form.errors.items():
                label = next((lbl for lbl, f, *_ in COLUMNS if f == field), "Ligne")
                errors += [f"{label} : {m}" for m in messages]
        reg = " ".join(str(data.get("registration_number", "")).upper().split())
        if reg and reg in seen:
            errors.append(f"Immatriculation en double dans le fichier (déjà ligne {seen[reg]}).")
        seen.setdefault(reg, line_number)
        results.append({"line": line_number, "data": data, "form": form, "errors": errors,
                        "label": f"{data.get('registration_number', '')} — {data.get('brand', '')} {data.get('model', '')}"})
    if not results:
        return [], "Le fichier ne contient aucun véhicule."
    return results, None


@transaction.atomic
def import_rows(rows):
    """Enregistre toutes les lignes (appelé seulement si aucune ne contient d'erreur)."""
    return [row["form"].save() for row in rows]

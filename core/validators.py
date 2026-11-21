"""Validateurs réutilisables pour sécuriser les fichiers téléversés."""
import os

from django.core.exceptions import ValidationError

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
DOCUMENT_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
MAX_IMAGE_SIZE = 2 * 1024 * 1024      # 2 Mo
MAX_DOCUMENT_SIZE = 5 * 1024 * 1024   # 5 Mo


def _check(file, allowed_extensions, max_size, label):
    extension = os.path.splitext(file.name)[1].lower()
    if extension not in allowed_extensions:
        raise ValidationError(
            f"Format de {label} non autorisé ({extension or 'aucune extension'}). "
            f"Formats acceptés : {', '.join(sorted(allowed_extensions))}."
        )
    if file.size > max_size:
        raise ValidationError(
            f"Le fichier est trop volumineux ({file.size // 1024} Ko). "
            f"Taille maximale : {max_size // (1024 * 1024)} Mo."
        )


def validate_image_file(file):
    """Photo : JPG, PNG ou WEBP, 2 Mo maximum (le contenu est vérifié par Pillow)."""
    _check(file, IMAGE_EXTENSIONS, MAX_IMAGE_SIZE, "photo")


def validate_document_file(file):
    """Justificatif : PDF, JPG ou PNG, 5 Mo maximum."""
    _check(file, DOCUMENT_EXTENSIONS, MAX_DOCUMENT_SIZE, "document")
    if os.path.splitext(file.name)[1].lower() == ".pdf":
        file.seek(0)
        header = file.read(5)
        file.seek(0)
        if header != b"%PDF-":
            raise ValidationError("Le fichier PDF semble invalide ou corrompu.")

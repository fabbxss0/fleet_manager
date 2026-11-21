"""Outils communs aux formulaires : style Bootstrap automatique et champs date HTML5."""
from django import forms


class DateInput(forms.DateInput):
    """Sélecteur de date natif (affiché JJ/MM/AAAA par le navigateur en français)."""
    input_type = "date"

    def __init__(self, attrs=None):
        super().__init__(attrs=attrs, format="%Y-%m-%d")


class BootstrapFormMixin:
    """Ajoute automatiquement les classes CSS Bootstrap à tous les champs du formulaire."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, (forms.CheckboxInput,)):
                css = "form-check-input"
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                css = "form-select"
            else:
                css = "form-control"
            widget.attrs["class"] = f"{widget.attrs.get('class', '')} {css}".strip()
            if isinstance(widget, forms.Textarea):
                widget.attrs.setdefault("rows", 3)
            if isinstance(field, forms.DateField) and not isinstance(widget, DateInput):
                field.widget = DateInput(attrs=widget.attrs)

    def full_clean(self):
        # On marque les champs en erreur APRÈS la validation (et non dans __init__,
        # ce qui déclencherait la validation trop tôt).
        super().full_clean()
        for name in self.errors:
            if name in self.fields:
                css = self.fields[name].widget.attrs.get("class", "")
                if "is-invalid" not in css:
                    self.fields[name].widget.attrs["class"] = f"{css} is-invalid".strip()

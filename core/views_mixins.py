"""Mixins génériques pour éviter la duplication dans les vues CRUD."""
from django.contrib import messages
from django.db.models import ProtectedError
from django.shortcuts import redirect
from django.views.generic import DeleteView


class PageTitleMixin:
    page_title = ""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("page_title", self.page_title)
        return context


class FormMessagesMixin:
    """Affiche un message de succès / d'erreur lors de l'envoi d'un formulaire."""
    success_message = "Enregistrement effectué avec succès."

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, self.success_message)
        return response

    def form_invalid(self, form):
        messages.error(self.request, "Le formulaire contient des erreurs. Veuillez les corriger.")
        return super().form_invalid(form)


class SafeDeleteView(DeleteView):
    """
    Suppression par POST uniquement (confirmée par une fenêtre modale).
    Si l'élément possède un historique protégé (PROTECT), la suppression est
    refusée avec un message clair au lieu d'une erreur serveur.
    """
    http_method_names = ["post"]
    success_message = "Suppression effectuée."
    protected_message = "Suppression impossible : cet élément possède un historique lié."

    def form_valid(self, form):
        self.object = self.get_object()
        try:
            self.object.delete()
        except ProtectedError:
            messages.error(self.request, self.protected_message)
            return redirect(self.object.get_absolute_url())
        messages.success(self.request, self.success_message)
        return redirect(self.get_success_url())


class FilteredListMixin:
    """Liste paginée avec recherche (?q=) et filtres simples (?champ=valeur)."""
    paginate_by = 10
    search_fields = ()
    filter_fields = ()  # noms de paramètres GET = noms de champs du modèle

    def get_queryset(self):
        from django.db.models import Q

        queryset = super().get_queryset()
        query = self.request.GET.get("q", "").strip()
        if query and self.search_fields:
            condition = Q()
            for field in self.search_fields:
                condition |= Q(**{f"{field}__icontains": query})
            queryset = queryset.filter(condition)
        for field in self.filter_fields:
            value = self.request.GET.get(field)
            if value:
                queryset = queryset.filter(**{field: value})
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["current_filters"] = {f: self.request.GET.get(f, "") for f in self.filter_fields}
        context["q"] = self.request.GET.get("q", "")
        context["result_count"] = context["paginator"].count if context.get("paginator") else len(context["object_list"])
        return context

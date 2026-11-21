from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.views.generic import ListView

from core.permissions import StaffRequiredMixin, staff_required
from core.views_mixins import PageTitleMixin

from .models import Alert
from .services import generate_alerts


class AlertListView(StaffRequiredMixin, PageTitleMixin, ListView):
    model = Alert
    template_name = "alerts/alert_list.html"
    page_title = "Alertes"
    paginate_by = 15

    def get_queryset(self):
        queryset = Alert.objects.select_related("vehicle", "driver", "assignment", "insurance", "maintenance")
        params = self.request.GET
        # Par défaut on affiche les alertes actives ; ?etat=resolues pour l'historique
        queryset = queryset.filter(is_resolved=params.get("etat") == "resolues")
        if params.get("priorite"):
            queryset = queryset.filter(priority=params["priorite"])
        if params.get("categorie"):
            queryset = queryset.filter(category=params["categorie"])
        if params.get("lecture") == "non_lues":
            queryset = queryset.filter(is_read=False)
        elif params.get("lecture") == "lues":
            queryset = queryset.filter(is_read=True)
        if params.get("q"):
            queryset = queryset.filter(title__icontains=params["q"])
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["priorities"] = Alert.Priority.choices
        context["categories"] = Alert.Category.choices
        context["params"] = self.request.GET
        open_alerts = Alert.objects.filter(is_resolved=False)
        context["priority_counts"] = [
            (value, label, open_alerts.filter(priority=value).count()) for value, label in Alert.Priority.choices
        ][::-1]
        return context


@staff_required
def alert_open(request, pk):
    """Marque l'alerte comme lue puis redirige vers l'élément concerné."""
    alert = get_object_or_404(Alert, pk=pk)
    if not alert.is_read:
        alert.is_read = True
        alert.save(update_fields=["is_read"])
    return redirect(alert.target_url)


def _back(request):
    referer = request.META.get("HTTP_REFERER", "")
    from django.utils.http import url_has_allowed_host_and_scheme

    if referer and url_has_allowed_host_and_scheme(referer, allowed_hosts={request.get_host()}):
        return redirect(referer)
    return redirect("alerts:list")


@staff_required
@require_POST
def alert_toggle_read(request, pk):
    alert = get_object_or_404(Alert, pk=pk)
    alert.is_read = not alert.is_read
    alert.save(update_fields=["is_read"])
    messages.success(request, "Alerte marquée comme lue." if alert.is_read else "Alerte marquée comme non lue.")
    return _back(request)


@staff_required
@require_POST
def alert_mark_all_read(request):
    count = Alert.objects.filter(is_resolved=False, is_read=False).update(is_read=True)
    messages.success(request, f"{count} alerte(s) marquée(s) comme lue(s).")
    return _back(request)


@staff_required
@require_POST
def alert_refresh(request):
    result = generate_alerts()
    messages.success(request, f"Vérification des échéances terminée : {result['created']} nouvelle(s) alerte(s), "
                              f"{result['resolved']} résolue(s).")
    return _back(request)

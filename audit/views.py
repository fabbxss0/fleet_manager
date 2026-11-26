from django.db.models import Q
from django.views.generic import ListView

from accounts.models import User
from core.filters import filter_period, parse_int
from core.permissions import AdminRequiredMixin
from core.views_mixins import PageTitleMixin

from .models import AuditLog


class AuditLogListView(AdminRequiredMixin, PageTitleMixin, ListView):
    """Journal complet, réservé à l'administrateur."""
    model = AuditLog
    template_name = "audit/audit_list.html"
    page_title = "Journal d'audit"
    paginate_by = 25

    def get_queryset(self):
        queryset = AuditLog.objects.select_related("user")
        p = self.request.GET
        if p.get("q"):
            queryset = queryset.filter(Q(object_repr__icontains=p["q"]) | Q(username__icontains=p["q"]))
        if p.get("action"):
            queryset = queryset.filter(action=p["action"])
        if p.get("type"):
            queryset = queryset.filter(model_label=p["type"])
        if parse_int(p.get("user")):
            queryset = queryset.filter(user_id=parse_int(p["user"]))
        queryset = filter_period(queryset, p, field="timestamp__date")
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["params"] = self.request.GET
        context["actions"] = AuditLog.Action.choices
        context["types"] = AuditLog.objects.exclude(model_label="").values_list("model_label", "model_name") \
            .distinct().order_by("model_name")
        context["users"] = User.objects.filter(audit_logs__isnull=False).distinct()
        context["result_count"] = context["paginator"].count
        return context

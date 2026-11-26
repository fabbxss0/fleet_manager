"""Routes principales de FLEET MANAGER."""
from django.contrib import admin
from django.templatetags.static import static
from django.urls import include, path, re_path
from django.views.generic import RedirectView

from core.views import protected_media

urlpatterns = [
    # Les navigateurs demandent /favicon.ico d'office : on renvoie vers l'icône de l'application
    path("favicon.ico", RedirectView.as_view(url=static("img/favicon.svg"), permanent=True)),
    path("admin/", admin.site.urls),
    path("", include("dashboard.urls")),
    path("comptes/", include("accounts.urls")),
    path("vehicules/", include("vehicles.urls")),
    path("conducteurs/", include("drivers.urls")),
    path("affectations/", include("assignments.urls")),
    path("entretiens/", include("maintenance.urls")),
    path("assurances/", include("insurance.urls")),
    path("carburant/", include("fuel.urls")),
    path("sinistres/", include("claims.urls")),
    path("journal/", include("audit.urls")),
    path("alertes/", include("alerts.urls")),
    path("rapports/", include("reports.urls")),
    path("", include("core.urls")),
    # Les fichiers téléversés ne sont servis qu'aux utilisateurs connectés
    re_path(r"^media/(?P<path>.*)$", protected_media, name="protected_media"),
]

handler403 = "core.views.error_403"
handler404 = "core.views.error_404"

"""
Rafraîchissement automatique des alertes.

Pour que l'application fonctionne même sans tâche planifiée, les alertes sont
régénérées lors de la navigation d'un utilisateur connecté, au plus une fois
toutes les ALERTS_AUTO_REFRESH_MINUTES minutes (mémorisé dans le cache).
"""
from django.conf import settings
from django.core.cache import cache

from .services import generate_alerts

CACHE_KEY = "alerts:last_auto_refresh"


class AlertAutoRefreshMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and not request.path.startswith(("/static/", "/media/")):
            timeout = settings.ALERTS_AUTO_REFRESH_MINUTES * 60
            # cache.add n'écrit que si la clé n'existe pas : une seule régénération par période
            if timeout > 0 and cache.add(CACHE_KEY, True, timeout):
                try:
                    generate_alerts()
                except Exception:  # une erreur d'alerte ne doit jamais bloquer la navigation
                    cache.delete(CACHE_KEY)
        return self.get_response(request)

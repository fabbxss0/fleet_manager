from .context import reset_request_context, set_request_context


def client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    return forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")


class CurrentUserMiddleware:
    """Rend l'utilisateur connecté et son adresse IP disponibles pour le journal d'audit."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tokens = set_request_context(getattr(request, "user", None), client_ip(request))
        try:
            return self.get_response(request)
        finally:
            reset_request_context(tokens)

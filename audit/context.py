"""
Mémorise « qui agit » pendant le traitement d'une requête.

Les signaux Django (post_save…) ne reçoivent pas la requête HTTP : on stocke
donc l'utilisateur courant dans une variable de contexte (contextvars), remplie
par le middleware au début de chaque requête. Une ContextVar est propre à
chaque requête, même si le serveur en traite plusieurs en parallèle.
"""
from contextlib import contextmanager
from contextvars import ContextVar

_current_user = ContextVar("audit_current_user", default=None)
_current_ip = ContextVar("audit_current_ip", default=None)
_disabled = ContextVar("audit_disabled", default=False)


def set_request_context(user, ip):
    return _current_user.set(user), _current_ip.set(ip)


def reset_request_context(tokens):
    _current_user.reset(tokens[0])
    _current_ip.reset(tokens[1])


def get_current_user():
    user = _current_user.get()
    return user if user is not None and user.is_authenticated else None


def get_current_ip():
    return _current_ip.get()


def is_disabled():
    return _disabled.get()


@contextmanager
def audit_disabled():
    """Suspend la journalisation (ex. chargement des données de démonstration)."""
    token = _disabled.set(True)
    try:
        yield
    finally:
        _disabled.reset(token)

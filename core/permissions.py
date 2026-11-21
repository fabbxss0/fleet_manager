"""
Contrôle d'accès par rôle.

- StaffRequiredMixin / staff_required : administrateurs et gestionnaires.
- AdminRequiredMixin / admin_required : administrateurs uniquement.
Un utilisateur non connecté est redirigé vers la page de connexion ; un
utilisateur connecté sans le bon rôle reçoit une erreur 403.
"""
from functools import wraps

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied


def user_has_role(user, roles):
    return user.is_authenticated and user.is_active and user.role in roles


class RoleRequiredMixin(LoginRequiredMixin):
    allowed_roles = ()

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not user_has_role(request.user, self.allowed_roles):
            raise PermissionDenied("Vous n'avez pas les droits nécessaires pour accéder à cette page.")
        return super().dispatch(request, *args, **kwargs)


class StaffRequiredMixin(RoleRequiredMixin):
    allowed_roles = ("ADMIN", "GESTIONNAIRE")


class AdminRequiredMixin(RoleRequiredMixin):
    allowed_roles = ("ADMIN",)


def role_required(*roles):
    """Décorateur équivalent pour les vues sous forme de fonctions."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            from django.contrib.auth.views import redirect_to_login

            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not user_has_role(request.user, roles):
                raise PermissionDenied("Vous n'avez pas les droits nécessaires pour accéder à cette page.")
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


staff_required = role_required("ADMIN", "GESTIONNAIRE")
admin_required = role_required("ADMIN")

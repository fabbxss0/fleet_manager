"""Authentification, profil et gestion des utilisateurs (administrateur)."""
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import SetPasswordForm
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, ListView, UpdateView

from core.forms import BootstrapFormMixin
from core.permissions import AdminRequiredMixin, admin_required
from core.views_mixins import FilteredListMixin, FormMessagesMixin, PageTitleMixin

from .forms import LoginForm, ProfileForm, StyledPasswordChangeForm, UserCreateForm, UserUpdateForm
from .models import User


class LoginView(auth_views.LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


@login_required
def profile_view(request):
    form = ProfileForm(request.POST or None, request.FILES or None, instance=request.user)
    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, "Votre profil a été mis à jour.")
            return redirect("accounts:profile")
        messages.error(request, "Le formulaire contient des erreurs.")
    return render(request, "accounts/profile.html", {"form": form, "page_title": "Mon profil"})


class PasswordChangeView(PageTitleMixin, auth_views.PasswordChangeView):
    template_name = "accounts/password_change.html"
    form_class = StyledPasswordChangeForm
    success_url = reverse_lazy("accounts:profile")
    page_title = "Changer mon mot de passe"

    def form_valid(self, form):
        messages.success(self.request, "Votre mot de passe a été modifié.")
        return super().form_valid(form)


# --- Gestion des utilisateurs (administrateur uniquement) -------------------
class UserListView(AdminRequiredMixin, PageTitleMixin, FilteredListMixin, ListView):
    model = User
    template_name = "accounts/user_list.html"
    page_title = "Utilisateurs"
    search_fields = ("username", "first_name", "last_name", "email")
    filter_fields = ("role",)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["roles"] = User.Role.choices
        return context


class UserCreateView(AdminRequiredMixin, PageTitleMixin, FormMessagesMixin, CreateView):
    model = User
    form_class = UserCreateForm
    template_name = "accounts/user_form.html"
    success_url = reverse_lazy("accounts:user_list")
    page_title = "Nouvel utilisateur"
    success_message = "Utilisateur créé avec succès."


class UserUpdateView(AdminRequiredMixin, PageTitleMixin, FormMessagesMixin, UpdateView):
    model = User
    form_class = UserUpdateForm
    template_name = "accounts/user_form.html"
    success_url = reverse_lazy("accounts:user_list")
    page_title = "Modifier l'utilisateur"
    success_message = "Utilisateur mis à jour."

    def form_valid(self, form):
        # Un administrateur ne peut pas se retirer lui-même ses droits ni se désactiver
        if form.instance.pk == self.request.user.pk and (
            form.cleaned_data["role"] != User.Role.ADMIN or not form.cleaned_data["is_active"]
        ):
            form.add_error(None, "Vous ne pouvez pas retirer vos propres droits d'administrateur ni désactiver votre compte.")
            return self.form_invalid(form)
        return super().form_valid(form)


class AdminSetPasswordForm(BootstrapFormMixin, SetPasswordForm):
    pass


@admin_required
def user_set_password(request, pk):
    target = get_object_or_404(User, pk=pk)
    form = AdminSetPasswordForm(target, request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Mot de passe de {target.username} réinitialisé.")
        return redirect("accounts:user_list")
    return render(request, "accounts/user_set_password.html", {
        "form": form, "target": target, "page_title": "Réinitialiser le mot de passe",
    })


@admin_required
@require_POST
def user_delete(request, pk):
    target = get_object_or_404(User, pk=pk)
    if target == request.user:
        messages.error(request, "Vous ne pouvez pas supprimer votre propre compte.")
    else:
        target.delete()
        messages.success(request, f"Le compte « {target.username} » a été supprimé.")
    return redirect("accounts:user_list")

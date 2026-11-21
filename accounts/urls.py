from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("connexion/", views.LoginView.as_view(), name="login"),
    path("deconnexion/", auth_views.LogoutView.as_view(), name="logout"),
    path("profil/", views.profile_view, name="profile"),
    path("mot-de-passe/", views.PasswordChangeView.as_view(), name="password_change"),
    path("utilisateurs/", views.UserListView.as_view(), name="user_list"),
    path("utilisateurs/nouveau/", views.UserCreateView.as_view(), name="user_create"),
    path("utilisateurs/<int:pk>/modifier/", views.UserUpdateView.as_view(), name="user_update"),
    path("utilisateurs/<int:pk>/mot-de-passe/", views.user_set_password, name="user_set_password"),
    path("utilisateurs/<int:pk>/supprimer/", views.user_delete, name="user_delete"),
]

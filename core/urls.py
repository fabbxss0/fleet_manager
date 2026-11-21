from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("recherche/", views.global_search, name="search"),
    path("parametres/", views.settings_view, name="settings"),
]

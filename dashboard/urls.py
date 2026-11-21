from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.home, name="home"),
    path("tableau-de-bord/", views.dashboard, name="dashboard"),
    path("mon-espace/", views.driver_space, name="driver_space"),
]

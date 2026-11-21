from django.urls import path

from . import views

app_name = "fuel"

urlpatterns = [
    path("", views.FuelListView.as_view(), name="list"),
    path("consommation/", views.fuel_stats, name="stats"),
    path("nouveau/", views.FuelCreateView.as_view(), name="create"),
    path("declarer/", views.driver_fuel_declare, name="driver_declare"),
    path("<int:pk>/modifier/", views.FuelUpdateView.as_view(), name="update"),
    path("<int:pk>/supprimer/", views.fuel_delete, name="delete"),
]

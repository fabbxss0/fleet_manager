from django.urls import path

from . import views

app_name = "maintenance"

urlpatterns = [
    path("", views.MaintenanceListView.as_view(), name="list"),
    path("a-prevoir/", views.maintenance_due, name="due"),
    path("depenses/", views.maintenance_expenses, name="expenses"),
    path("nouveau/", views.MaintenanceCreateView.as_view(), name="create"),
    path("<int:pk>/", views.MaintenanceDetailView.as_view(), name="detail"),
    path("<int:pk>/modifier/", views.MaintenanceUpdateView.as_view(), name="update"),
    path("<int:pk>/supprimer/", views.maintenance_delete, name="delete"),
]

from django.urls import path

from . import views

app_name = "drivers"

urlpatterns = [
    path("", views.DriverListView.as_view(), name="list"),
    path("nouveau/", views.DriverCreateView.as_view(), name="create"),
    path("<int:pk>/", views.DriverDetailView.as_view(), name="detail"),
    path("<int:pk>/modifier/", views.DriverUpdateView.as_view(), name="update"),
    path("<int:pk>/supprimer/", views.DriverDeleteView.as_view(), name="delete"),
]

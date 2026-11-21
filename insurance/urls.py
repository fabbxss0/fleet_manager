from django.urls import path

from . import views

app_name = "insurance"

urlpatterns = [
    path("", views.InsuranceListView.as_view(), name="list"),
    path("nouvelle/", views.InsuranceCreateView.as_view(), name="create"),
    path("<int:pk>/", views.InsuranceDetailView.as_view(), name="detail"),
    path("<int:pk>/modifier/", views.InsuranceUpdateView.as_view(), name="update"),
    path("<int:pk>/supprimer/", views.InsuranceDeleteView.as_view(), name="delete"),
]

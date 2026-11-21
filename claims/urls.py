from django.urls import path

from . import views

app_name = "claims"

urlpatterns = [
    path("", views.ClaimListView.as_view(), name="list"),
    path("nouveau/", views.ClaimCreateView.as_view(), name="create"),
    path("<int:pk>/", views.ClaimDetailView.as_view(), name="detail"),
    path("<int:pk>/modifier/", views.ClaimUpdateView.as_view(), name="update"),
    path("<int:pk>/supprimer/", views.claim_delete, name="delete"),
]

from django.urls import path

from . import views

app_name = "assignments"

urlpatterns = [
    path("", views.AssignmentListView.as_view(), name="list"),
    path("nouvelle/", views.AssignmentCreateView.as_view(), name="create"),
    path("planning/", views.assignment_planning, name="planning"),
    path("<int:pk>/", views.AssignmentDetailView.as_view(), name="detail"),
    path("<int:pk>/modifier/", views.AssignmentUpdateView.as_view(), name="update"),
    path("<int:pk>/retour/", views.assignment_return, name="return"),
    path("<int:pk>/annuler/", views.assignment_cancel, name="cancel"),
]

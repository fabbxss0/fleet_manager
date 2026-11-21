from django.urls import path

from . import views

app_name = "alerts"

urlpatterns = [
    path("", views.AlertListView.as_view(), name="list"),
    path("<int:pk>/ouvrir/", views.alert_open, name="open"),
    path("<int:pk>/lecture/", views.alert_toggle_read, name="toggle_read"),
    path("tout-marquer-lu/", views.alert_mark_all_read, name="mark_all_read"),
    path("verifier/", views.alert_refresh, name="refresh"),
]

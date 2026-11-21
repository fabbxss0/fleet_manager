from django.contrib import admin

from .models import Maintenance


@admin.register(Maintenance)
class MaintenanceAdmin(admin.ModelAdmin):
    list_display = ("vehicle", "intervention_type", "date", "cost", "status")
    list_filter = ("intervention_type", "status")

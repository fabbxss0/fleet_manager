from django.contrib import admin

from .models import FuelEntry


@admin.register(FuelEntry)
class FuelEntryAdmin(admin.ModelAdmin):
    list_display = ("vehicle", "date", "mileage", "liters", "total_amount", "station")
    list_filter = ("full_tank",)

from django.contrib import admin

from .models import Vehicle


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ("registration_number", "brand", "model", "category", "status", "mileage")
    list_filter = ("category", "status", "fuel_type")
    search_fields = ("registration_number", "brand", "model", "chassis_number")

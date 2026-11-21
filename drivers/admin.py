from django.contrib import admin

from .models import Driver


@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = ("last_name", "first_name", "license_number", "license_expiry_date", "status")
    list_filter = ("status", "license_category")
    search_fields = ("last_name", "first_name", "license_number")

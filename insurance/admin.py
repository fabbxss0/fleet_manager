from django.contrib import admin

from .models import Insurance


@admin.register(Insurance)
class InsuranceAdmin(admin.ModelAdmin):
    list_display = ("vehicle", "company", "policy_number", "start_date", "end_date")
    search_fields = ("policy_number", "company")

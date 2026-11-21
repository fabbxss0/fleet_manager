from django.contrib import admin

from .models import Claim


@admin.register(Claim)
class ClaimAdmin(admin.ModelAdmin):
    list_display = ("vehicle", "claim_type", "date", "status", "insurance_status", "estimated_cost")
    list_filter = ("claim_type", "status", "insurance_status")

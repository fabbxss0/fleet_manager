from django.contrib import admin

from .models import Alert


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "priority", "is_read", "is_resolved", "created_at")
    list_filter = ("category", "priority", "is_read", "is_resolved")

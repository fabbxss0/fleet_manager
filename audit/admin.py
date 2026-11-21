from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Consultation seule : le journal ne se modifie pas."""
    list_display = ("timestamp", "username", "action", "model_name", "object_repr", "ip_address")
    list_filter = ("action", "model_name")
    search_fields = ("object_repr", "username")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

from django.contrib import admin

from .models import Assignment


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ("vehicle", "driver", "start_date", "expected_end_date", "status")
    list_filter = ("status",)

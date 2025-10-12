"""
Core admin configuration.
"""
from django.contrib import admin


class TimeStampedAdmin(admin.ModelAdmin):
    """Base admin class for timestamped models."""
    readonly_fields = ('created_at', 'updated_at')
    list_display_links = None

    def get_list_display(self, request):
        list_display = super().get_list_display(request)
        if list_display == ('__str__',):
            return list_display
        return list(list_display) + ['created_at', 'updated_at']


class ReadOnlyAdmin(admin.ModelAdmin):
    """Base admin class for read-only models."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
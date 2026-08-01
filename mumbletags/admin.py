from django.contrib import admin
from django.utils.html import format_html

from .models import TagAssociation

MAX_SHOWN_GROUPS = 10


@admin.register(TagAssociation)
class TagAssociationAdmin(admin.ModelAdmin):
    list_display = ["tag", "enabled", "position", "order", "_groups"]
    list_filter = ["enabled", "position"]
    search_fields = ["tag"]
    filter_horizontal = ["groups"]

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("groups")

    @admin.display(description="groups")
    def _groups(self, obj) -> str:
        names = sorted(group.name for group in obj.groups.all())
        if not names:
            return "-"
        if len(names) <= MAX_SHOWN_GROUPS:
            return ", ".join(names)
        return format_html(
            '<span title="{}">{}, (...)</span>',
            ", ".join(names),
            ", ".join(names[:MAX_SHOWN_GROUPS]),
        )

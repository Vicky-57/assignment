from django.contrib import admin
from .models import LayoutTemplate, DesignRecommendation

@admin.register(LayoutTemplate)
class LayoutTemplateAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "room_type", "style")

@admin.register(DesignRecommendation)
class DesignRecommendationAdmin(admin.ModelAdmin):
    list_display = ("id", "session", "layout_template_id", "get_layout_template_name", "status", "created_at")
    search_fields = ("id", "session__id", "layout_template__name")
    list_filter = ("status", "created_at")

    def get_layout_template_name(self, obj):
        return obj.layout_template.name if obj.layout_template else "-"
    get_layout_template_name.short_description = "Layout Template Name"


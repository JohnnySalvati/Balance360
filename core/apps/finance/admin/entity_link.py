
from django.contrib import admin
from ..models import entity_link

@admin.register(entity_link.EconomicEntityLink)
class EconomicEntityLinkAdmin(admin.ModelAdmin):
    list_display = ("parent", "child")
    list_filter = ("parent", "child")
    search_fields = ("parent__name", "child__name")
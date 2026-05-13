from django.contrib import admin
from .models import Ville, Agence


@admin.register(Ville)
class VilleAdmin(admin.ModelAdmin):
    list_display = ["nom", "region", "prioritaire", "active"]
    search_fields = ["nom", "region"]
    list_filter = ["prioritaire", "region", "active"]


@admin.register(Agence)
class AgenceAdmin(admin.ModelAdmin):
    list_display = ["nom", "ville", "code", "active", "date_creation"]
    search_fields = ["nom", "ville__nom", "code"]
    list_filter = ["ville", "active"]

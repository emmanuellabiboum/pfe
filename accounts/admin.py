from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, OTPCode, LoginActivity, AdminVille


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ["username", "email", "role", "ville", "agence", "statut"]
    list_filter = ["role", "statut", "ville", "agence"]
    
    def get_fieldsets(self, request, obj=None):
        fieldsets = list(UserAdmin.fieldsets)
        extra_fields = ["role", "ville", "statut", "telephone", "valide_par"]
        
        # Si c'est un admin existant ou nouveau avec rôle admin/super_admin
        # on n'affiche pas le champ agence
        if obj and obj.role in ["admin", "super_admin"]:
            extra_fields = ["role", "ville", "statut", "telephone", "valide_par"]
        elif obj and obj.role in ["chef_agence", "agent_marketing", "agent_commercial"]:
            extra_fields = ["role", "ville", "agence", "statut", "telephone", "valide_par"]
        else:
            # Pour les nouveaux utilisateurs, on affiche tout
            extra_fields = ["role", "ville", "agence", "statut", "telephone", "valide_par"]
        
        fieldsets.append(
            ("Informations supplémentaires", {"fields": extra_fields})
        )
        return fieldsets
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Aide contextuelle sur le champ ville selon le rôle
        if obj and obj.role in ["admin", "super_admin"]:
            if 'ville' in form.base_fields:
                form.base_fields['ville'].help_text = "L'administrateur gère toute cette ville"
            if 'agence' in form.base_fields:
                form.base_fields['agence'].widget = forms.HiddenInput()
        return form


@admin.register(OTPCode)
class OTPCodeAdmin(admin.ModelAdmin):
    list_display = ["user", "code", "expire_at", "created_at"]
    search_fields = ["user__username", "code"]
    list_filter = ["created_at", "expire_at"]


@admin.register(LoginActivity)
class LoginActivityAdmin(admin.ModelAdmin):
    list_display = ["user", "timestamp"]
    search_fields = ["user__username"]
    list_filter = ["timestamp"]


@admin.register(AdminVille)
class AdminVilleAdmin(admin.ModelAdmin):
    list_display = ["user", "ville", "actif", "date_nomination"]
    list_filter = ["actif", "ville"]
    search_fields = ["user__username", "user__first_name", "user__last_name", "ville__nom"]
    raw_id_fields = ["user"]

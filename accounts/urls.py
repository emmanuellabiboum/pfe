from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("inscription/", views.inscription_view, name="inscription"),
    path("verify-otp/", views.verify_otp_view, name="verify_otp"),
    path("assign-agence/", views.assign_agence, name="assign_agence"),
    path("reset-password/", views.reset_password_view, name="reset_password"),
    path("roles-disponibles/", views.roles_disponibles, name="roles_disponibles"),
    path("gestion-comptes/", views.gestion_comptes_view, name="gestion_comptes"),
    path(
        "action-compte/<int:user_id>/", views.action_compte_view, name="action_compte"
    ),
    path("profile/", views.profile_view, name="profile"),
]

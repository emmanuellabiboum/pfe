from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.utils import timezone
import random
from datetime import timedelta
from django.db.models import Q
from .models import User, OTPCode, AdminVille

OTP_RESET_PASSWORD_DURATION_MINUTES = 5
from core.models import Ville, Agence
from dashboard.models import Notification
from .email_utils import envoyer_email
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from accounts.forms import AgenceForm
from dashboard.models import AnalyseSession, Recommandation
from learning.models import ClientChurn


def creer_notifications_bienvenue(user):
    nom = user.get_full_name() or user.username
    role = user.get_role_display()
    agence = user.agence.nom if user.agence else "—"

    # Pour les admins, récupérer la ville via AdminVille
    admin_ville = None
    if user.role in ["admin", "super_admin"]:
        try:
            admin_ville = user.admin_ville.ville
        except AdminVille.DoesNotExist:
            pass

    if user.role == "admin":
        scope = f"pour la ville {admin_ville.nom}" if admin_ville else ""
    else:
        scope = f"pour l'agence {agence}"

    Notification.objects.create(
        destinataire=user,
        type_notif="compte",
        titre=f"Bienvenue {nom} !",
        contenu=(
            f"Votre compte {role} {scope} a été activé avec succès. "
            f"Vous pouvez maintenant vous connecter et commencer à utiliser la plateforme."
        ),
        lien="/",
    )

    if user.role == "admin":
        ville_nom = admin_ville.nom if admin_ville else "votre ville"
        guide = (
            f"En tant qu'administrateur de {ville_nom}, vous pouvez : "
            "• Valider les comptes des chefs d'agence de votre ville ; "
            "• Superviser toutes les agences de votre périmètre ; "
            "• Consulter le dashboard global de votre ville."
        )
    elif user.is_superuser:
        guide = (
            "En tant que super administrateur, vous pouvez : "
            "• Valider les comptes admin de toutes les villes ; "
            "• Accéder à l'interface d'administration Django ; "
            "• Gérer toutes les données du système."
        )
    elif user.role == "chef_agence":
        guide = (
            "En tant que chef d'agence, vous pouvez : "
            "• Valider les comptes des agents de votre agence ; "
            "• Valider ou rejeter les recommandations IA générées pour vos clients ; "
            "• Suivre l'avancement des missions de vos agents ; "
            "• Consulter le dashboard et les fiches clients de votre agence."
        )
    elif user.role == "agent_marketing":
        guide = (
            "En tant qu'agent marketing, vous pouvez : "
            "• Consulter les missions marketing qui vous sont assignées ; "
            "• Voir les fiches clients avec les recommandations IA ; "
            "• Marquer les missions comme complétées une fois traitées ; "
            "• Accéder au dashboard pour suivre les indicateurs churn."
        )
    elif user.role == "agent_commercial":
        guide = (
            "En tant qu'agent commercial, vous pouvez : "
            "• Consulter les missions commerciales qui vous sont assignées ; "
            "• Proposer des plans d'échelonnement ou des offres adaptées ; "
            "• Marquer les missions comme complétées une fois traitées ; "
            "• Accéder au dashboard pour suivre les indicateurs churn."
        )
    else:
        guide = "Consultez le dashboard et les fiches clients pour commencer."

    Notification.objects.create(
        destinataire=user,
        type_notif="info",
        titre="Guide d'utilisation — " + role,
        contenu=guide,
        lien="/",
    )

    Notification.objects.create(
        destinataire=user,
        type_notif="info",
        titre="Politique de confidentialité",
        contenu=(
            "En utilisant cette application, vous acceptez notre politique de confidentialité : "
            "• Les données clients sont strictement confidentielles et ne doivent pas être partagées en dehors de l'entreprise ; "
            "• Les prédictions de churn sont réservées à un usage interne uniquement ; "
            "• Toute divulgation de données à un tiers est strictement interdite et peut entraîner des sanctions disciplinaires ; "
            "• Vous êtes responsable de la sécurité de vos identifiants de connexion."
        ),
        lien="/",
    )


def generer_notifications_agent(user):

    if not user.agence or user.role not in ["agent_marketing", "agent_commercial"]:
        return

    agence = user.agence

    derniere_analyse = (
        AnalyseSession.objects.filter(agence=agence).order_by("-date_analyse").first()
    )

    if derniere_analyse:
        clients_agence = ClientChurn.objects.filter(dataset__agence=agence)
        total_clients = clients_agence.count()
        clients_risque = clients_agence.filter(score_churn__gte=0.5).count()
        taux_churn = round(
            (clients_risque / total_clients * 100) if total_clients > 0 else 0, 1
        )

        contenu_stats = (
            f"Dernière analyse du {derniere_analyse.date_analyse.strftime('%d/%m/%Y')} : "
            f"{total_clients} clients, {clients_risque} à risque ({taux_churn}%). "
            f"Consultez le dashboard pour plus de détails."
        )

        notif_existante = Notification.objects.filter(
            destinataire=user,
            type_notif="alerte_churn",
            titre__icontains="Résultats analyse",
            date_creation__gte=timezone.now() - timedelta(hours=24),
        ).exists()

        if not notif_existante:
            Notification.objects.create(
                destinataire=user,
                type_notif="alerte_churn",
                titre="Résultats analyse — " + agence.nom,
                contenu=contenu_stats,
                lien="/",
            )


def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        try:
            user = User.objects.get(username=username)
            if user.est_bloque:
                messages.error(request, "Compte bloqué. Contactez l'administrateur.")
                return render(request, "accounts/login.html")
        except User.DoesNotExist:
            messages.error(request, "Identifiants incorrects.")
            return render(request, "accounts/login.html")

        if user.statut != "actif" and not user.is_superuser:
            messages.error(request, "Votre compte est en attente de validation.")
            return render(request, "accounts/login.html")

        auth_user = authenticate(request, username=username, password=password)

        if auth_user is not None:
            user.tentatives_connexion = 0
            user.save()

            code = str(random.randint(100000, 999999))
            OTPCode.objects.filter(user=user).delete()
            OTPCode.objects.create(
                user=user, code=code, expire_at=timezone.now() + timedelta(minutes=5)
            )
            envoyer_email(
                destinataire=user.email,
                sujet="Code de vérification — Tunisie Telecom",
                contenu=f"<p>Votre code de vérification est : <strong>{code}</strong></p><p>Valable 5 minutes.</p>",
            )
            request.session["otp_user_id"] = user.id
            return redirect("accounts:verify_otp")

        else:
            user.tentatives_connexion += 1
            if user.tentatives_connexion >= 3:
                user.est_bloque = True
                user.save()
                messages.error(
                    request,
                    "Compte bloqué après 3 tentatives. Contactez l'administrateur.",
                )
            else:
                restantes = 3 - user.tentatives_connexion
                user.save()
                messages.error(
                    request,
                    f"Mot de passe incorrect. {restantes} tentative(s) restante(s).",
                )

    return render(request, "accounts/login.html")


@login_required
def assign_agence(request):
    if request.method == "POST":
        form = AgenceForm(request.POST)
        if form.is_valid():
            request.user.agence = form.cleaned_data["agence"]
            request.user.save()
            messages.success(request, "Agence assignée avec succès !")
            return redirect("dashboard:accueil")
    else:
        form = AgenceForm()
    return render(request, "accounts/assign_agence.html", {"form": form})


def verify_otp_view(request):
    user_id = request.session.get("otp_user_id")
    if not user_id:
        return redirect("accounts:login")

    # Calculer le temps restant réel pour le timer
    otp_obj = OTPCode.objects.filter(user_id=user_id).first()
    remaining_seconds = 0
    if otp_obj:
        delta = otp_obj.expire_at - timezone.now()
        remaining_seconds = max(0, int(delta.total_seconds()))

    if request.method == "POST":
        code_saisi = request.POST.get("code")
        try:
            otp = OTPCode.objects.get(user_id=user_id, code=code_saisi)
            if otp.expire_at < timezone.now():
                messages.error(request, "Code expiré. Reconnectez-vous.")
                return redirect("accounts:login")

            user = User.objects.get(id=user_id)
            login(request, user)
            otp.delete()
            request.session.pop("otp_user_id", None)

            generer_notifications_agent(user)

            return redirect("dashboard:accueil")

        except OTPCode.DoesNotExist:
            messages.error(request, "Code incorrect.")

    return render(
        request, "accounts/verify_otp.html", {"remaining_seconds": remaining_seconds}
    )


def logout_view(request):
    logout(request)
    return redirect("accounts:login")


def inscription_view(request):
    villes = Ville.objects.filter(active=True)
    agences = Agence.objects.filter(active=True).select_related("ville")

    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")
        password2 = request.POST.get("password2")
        role = request.POST.get("role")
        ville_id = request.POST.get("ville")
        agence_id = request.POST.get("agence")
        telephone = request.POST.get("telephone")

        if password != password2:
            messages.error(request, "Les mots de passe ne correspondent pas.")
            return render(
                request,
                "accounts/inscription.html",
                {"villes": villes, "agences": agences},
            )

        user_data = {
            "username": username,
            "email": email,
            "password": password,
            "role": role,
            "telephone": telephone,
            "statut": "en_attente",
        }

        ville = None
        agence = None

        if role in ["admin", "super_admin"]:
            try:
                ville = Ville.objects.get(id=ville_id)
            except Ville.DoesNotExist:
                messages.error(request, "Ville invalide.")
                return render(
                    request,
                    "accounts/inscription.html",
                    {"villes": villes, "agences": agences},
                )

            admin_existant = AdminVille.objects.filter(
                ville=ville, user__role=role, user__statut__in=["actif", "en_attente"]
            ).exists()
            if admin_existant:
                role_display = (
                    "super administrateur" if role == "super_admin" else "admin"
                )
                messages.error(
                    request, f"Un {role_display} existe déjà pour la ville {ville.nom}."
                )
                return render(
                    request,
                    "accounts/inscription.html",
                    {"villes": villes, "agences": agences},
                )

            user_data["agence"] = None
            # La ville est gérée via AdminVille, pas directement sur User
        else:
            try:
                agence = Agence.objects.get(id=agence_id)
            except Agence.DoesNotExist:
                messages.error(request, "Agence invalide.")
                return render(
                    request,
                    "accounts/inscription.html",
                    {"villes": villes, "agences": agences},
                )

            ville = agence.ville

            role_pris = User.objects.filter(
                agence=agence, role=role, statut__in=["actif", "en_attente"]
            ).exists()
            if role_pris:
                messages.error(
                    request, f"Le rôle '{role}' est déjà pris dans cette agence."
                )
                return render(
                    request,
                    "accounts/inscription.html",
                    {"villes": villes, "agences": agences},
                )

            total = User.objects.filter(
                agence=agence, statut__in=["actif", "en_attente"]
            ).count()
            if total >= 3:
                messages.error(
                    request, "Cette agence a atteint la limite de 3 comptes."
                )
                return render(
                    request,
                    "accounts/inscription.html",
                    {"villes": villes, "agences": agences},
                )

            user_data["agence"] = agence
            user_data["ville"] = ville

        user = User.objects.create_user(**user_data)

        # Créer l'AdminVille pour les admins
        if role in ["admin", "super_admin"] and ville:
            AdminVille.objects.create(user=user, ville=ville)

        if role == "admin":
            superadmins = User.objects.filter(
                admin_ville__ville=ville, role="super_admin", statut="actif"
            )
            for sa in superadmins:
                envoyer_email(
                    destinataire=sa.email,
                    sujet="Nouvelle demande admin ville — Tunisie Telecom",
                    contenu=f"<p>Nouvel administrateur de ville en attente.<br>Utilisateur : <strong>{username}</strong><br>Ville : {ville.nom}<br>Téléphone : {telephone}</p>",
                )
                Notification.objects.create(
                    destinataire=sa,
                    type_notif="validation_requise",
                    titre=f"Validation admin — {ville.nom}",
                    contenu=f"Nouvel admin '{username}' pour {ville.nom} en attente.",
                    lien=f"/accounts/gestion-comptes/",
                )
            messages.success(
                request,
                f"Compte admin créé. En attente de validation pour {ville.nom}.",
            )

        elif role == "super_admin":
            superusers = User.objects.filter(is_superuser=True)
            for su in superusers:
                envoyer_email(
                    destinataire=su.email,
                    sujet="Nouvelle demande super admin — Tunisie Telecom",
                    contenu=f"<p>Nouveau super administrateur en attente.<br>Utilisateur : <strong>{username}</strong><br>Ville : {ville.nom}<br>Téléphone : {telephone}</p>",
                )
            messages.success(request, f"Compte super admin créé pour {ville.nom}.")

        elif role == "chef_agence":
            admins = User.objects.filter(ville=ville, role="admin", statut="actif")
            superadmins = User.objects.filter(
                ville=ville, role="super_admin", statut="actif"
            )

            destinataires = list(admins) + list(
                superadmins.exclude(id__in=admins.values_list("id", flat=True))
            )

            for admin in destinataires:
                envoyer_email(
                    destinataire=admin.email,
                    sujet="Nouvelle demande de chef d'agence — Tunisie Telecom",
                    contenu=f"<p>Nouveau chef d'agence en attente.<br>Utilisateur : <strong>{username}</strong><br>Agence : {agence.nom}<br>Ville : {ville.nom}<br>Téléphone : {telephone}</p>",
                )
                Notification.objects.create(
                    destinataire=admin,
                    type_notif="validation_requise",
                    titre=f"Validation chef d'agence — {agence.nom}",
                    contenu=f"Nouveau chef d'agence '{username}' pour l'agence {agence.nom} ({ville.nom}) en attente.",
                    lien=f"/accounts/gestion-comptes/",
                )
            messages.success(
                request,
                "Compte créé. En attente de validation par l'admin de la ville.",
            )
        else:
            chef = User.objects.filter(
                agence=agence, role="chef_agence", statut="actif"
            ).first()
            if chef:
                envoyer_email(
                    destinataire=chef.email,
                    sujet="Nouvelle demande de compte agent — Tunisie Telecom",
                    contenu=f"<p>Nouveau compte agent en attente.<br>Utilisateur : <strong>{username}</strong><br>Rôle : {role}<br>Agence : {agence.nom}<br>Téléphone : {telephone}</p>",
                )
                Notification.objects.create(
                    destinataire=chef,
                    type_notif="validation_requise",
                    titre=f"Validation {role} requise",
                    contenu=f"Nouveau '{role}' '{username}' pour votre agence {agence.nom} en attente.",
                    lien=f"/accounts/gestion-comptes/",
                )
            messages.success(
                request, "Compte créé. En attente de validation par le chef d'agence."
            )

        return redirect("accounts:login")

    return render(
        request, "accounts/inscription.html", {"villes": villes, "agences": agences}
    )


def reset_password_view(request):
    etape = "1"
    email = ""

    if request.method == "POST":
        etape = request.POST.get("etape", "1")
        email = request.POST.get("email", "")

        if etape == "1":
            try:
                user = User.objects.get(email=email)
                code = str(random.randint(100000, 999999))
                OTPCode.objects.filter(user=user).delete()
                OTPCode.objects.create(
                    user=user,
                    code=code,
                    expire_at=timezone.now()
                    + timedelta(minutes=OTP_RESET_PASSWORD_DURATION_MINUTES),
                )
                envoyer_email(
                    destinataire=email,
                    sujet="Réinitialisation mot de passe — Tunisie Telecom",
                    contenu=(
                        f"<p>Votre code de réinitialisation : <strong>{code}</strong><br>"
                        f"Valable {OTP_RESET_PASSWORD_DURATION_MINUTES} minute{'s' if OTP_RESET_PASSWORD_DURATION_MINUTES > 1 else ''}.</p>"
                    ),
                )
                etape = "2"
            except User.DoesNotExist:
                messages.error(request, "Aucun compte avec cet email.")
                etape = "1"

        elif etape == "2":
            code = request.POST.get("code")
            try:
                user = User.objects.get(email=email)
                otp = OTPCode.objects.get(user=user, code=code)
                if otp.expire_at < timezone.now():
                    messages.error(request, "Code expiré. Recommencez.")
                    etape = "1"
                else:
                    etape = "3"
            except (User.DoesNotExist, OTPCode.DoesNotExist):
                messages.error(request, "Code incorrect.")
                etape = "2"

        elif etape == "3":
            password = request.POST.get("password")
            password2 = request.POST.get("password2")
            if password != password2:
                messages.error(request, "Les mots de passe ne correspondent pas.")
                etape = "3"
            else:
                try:
                    user = User.objects.get(email=email)
                    user.set_password(password)
                    user.save()
                    OTPCode.objects.filter(user=user).delete()
                    messages.success(request, "Mot de passe changé avec succès !")
                    return redirect("accounts:login")
                except User.DoesNotExist:
                    messages.error(request, "Erreur. Recommencez.")
                    etape = "1"

    return render(
        request,
        "accounts/reset_password.html",
        {
            "etape": etape,
            "email": email,
            "otp_validity_minutes": OTP_RESET_PASSWORD_DURATION_MINUTES,
        },
    )


def roles_disponibles(request):
    agence_id = request.GET.get("agence_id")
    ville_id = request.GET.get("ville_id")

    pris = []

    if agence_id:
        pris = list(
            User.objects.filter(
                agence_id=agence_id, statut__in=["actif", "en_attente"]
            ).values_list("role", flat=True)
        )

    if ville_id:
        admin_existe = User.objects.filter(
            ville_id=ville_id, role="admin", statut__in=["actif", "en_attente"]
        ).exists()
        if admin_existe:
            pris.append("admin")

        superadmin_existe = User.objects.filter(
            ville_id=ville_id, role="super_admin", statut__in=["actif", "en_attente"]
        ).exists()
        if superadmin_existe:
            pris.append("super_admin")

    return JsonResponse({"pris": pris})


@login_required
def gestion_comptes_view(request):
    users = None
    stats = {}
    context = {}

    if request.user.role == "super_admin":
        # Super admin voit tous les admins ville et chefs d'agence
        users = (
            User.objects.filter(
                Q(role="admin") | Q(role="chef_agence"),
                statut__in=["en_attente", "actif"],
            )
            .exclude(id=request.user.id)
            .exclude(is_superuser=True)
            .select_related("agence", "agence__ville", "admin_ville__ville")
            .order_by("role", "statut", "date_demande")
        )

        stats = {
            "total": users.count(),
            "en_attente": users.filter(statut="en_attente").count(),
            "actifs": users.filter(statut="actif", est_bloque=False).count(),
            "bloques": users.filter(est_bloque=True).count(),
        }
        context = {"is_super_admin": True}

    elif request.user.role == "admin":
        # Récupérer la ville via AdminVille
        admin_ville_obj = (
            request.user.admin_ville.ville
            if hasattr(request.user, "admin_ville")
            else None
        )
        users = (
            User.objects.filter(
                role="chef_agence",
                agence__ville=admin_ville_obj,
                statut__in=["en_attente", "actif"],
            )
            .exclude(id=request.user.id)
            .exclude(is_superuser=True)
            .select_related("agence", "agence__ville")
            .order_by("statut", "date_demande")
        )

        stats = {
            "total": users.count(),
            "en_attente": users.filter(statut="en_attente").count(),
            "actifs": users.filter(statut="actif", est_bloque=False).count(),
            "bloques": users.filter(est_bloque=True).count(),
        }
        context = {"is_admin": True, "admin_ville": admin_ville_obj}

    elif request.user.role == "chef_agence":
        users = (
            User.objects.filter(agence=request.user.agence)
            .exclude(id=request.user.id)
            .exclude(role__in=["chef_agence", "admin"])
            .exclude(is_superuser=True)
            .order_by("est_bloque", "statut", "date_demande")
        )

        stats = {
            "total": users.count(),
            "en_attente": users.filter(statut="en_attente").count(),
            "actifs": users.filter(statut="actif", est_bloque=False).count(),
            "bloques": users.filter(est_bloque=True).count(),
        }
        chef_agence = request.user.agence if request.user.agence else None
        context = {"is_chef": True, "chef_agence": chef_agence}
    else:
        messages.error(
            request, "Vous n'avez pas les permissions pour accéder à cette page."
        )
        return redirect("/")

    return render(
        request,
        "accounts/gestion_comptes.html",
        {"users": users, "stats": stats, **context},
    )


@login_required
@require_POST
def action_compte_view(request, user_id):
    try:
        if request.user.role == "super_admin":
            user = User.objects.get(
                id=user_id,
                is_superuser=False,
            )
            if user.role not in ["admin", "chef_agence"]:
                raise User.DoesNotExist
        elif request.user.role == "admin":
            admin_ville_obj = (
                request.user.admin_ville.ville
                if hasattr(request.user, "admin_ville")
                else None
            )
            user = User.objects.get(
                id=user_id, role="chef_agence", agence__ville=admin_ville_obj
            )
        elif request.user.role == "chef_agence":
            user = User.objects.get(id=user_id, agence=request.user.agence)
            if user.role in ["chef_agence", "admin", "super_admin"]:
                messages.error(request, "Vous ne pouvez pas gérer ce type de compte.")
                return redirect("accounts:gestion_comptes")
        else:
            messages.error(request, "Permissions insuffisantes.")
            return redirect("/")
    except User.DoesNotExist:
        messages.error(request, "Utilisateur introuvable ou hors de votre périmètre.")
        return redirect("accounts:gestion_comptes")

    action = request.POST.get("action")

    if action == "valider":
        user.statut = "actif"
        user.est_bloque = False
        user.tentatives_connexion = 0
        user.date_validation = timezone.now()
        user.valide_par = request.user
        user.save()
        envoyer_email(
            destinataire=user.email,
            sujet="Compte validé — Tunisie Telecom",
            contenu=f'<p>Bonjour <strong>{user.get_full_name()}</strong>,</p><p>Votre compte a été <strong style="color:green">validé</strong>.</p><p>Vous pouvez maintenant vous connecter et consulter vos notifications pour découvrir l\'application.</p>',
        )
        creer_notifications_bienvenue(user)
        messages.success(
            request,
            f"Compte de {user.get_full_name()} validé. Notifications de bienvenue envoyées.",
        )

    elif action == "refuser":
        user.statut = "suspendu"
        user.save()
        envoyer_email(
            destinataire=user.email,
            sujet="Compte refusé — Tunisie Telecom",
            contenu=f'<p>Bonjour <strong>{user.get_full_name()}</strong>,</p><p>Votre demande a été <strong style="color:red">refusée</strong>.</p>',
        )
        messages.error(request, f"Compte de {user.get_full_name()} refusé.")

    elif action == "suspendre":
        user.statut = "suspendu"
        user.save()
        envoyer_email(
            destinataire=user.email,
            sujet="Compte suspendu — Tunisie Telecom",
            contenu=f'<p>Bonjour <strong>{user.get_full_name()}</strong>,</p><p>Votre compte a été <strong style="color:orange">suspendu</strong>.</p>',
        )
        messages.warning(request, f"Compte de {user.get_full_name()} suspendu.")

    elif action == "supprimer":
        nom_complet = user.get_full_name()
        user.delete()
        messages.success(request, f"Le compte de {nom_complet} a été supprimé définitivement de la base de données.")

    elif action == "debloquer":
        user.est_bloque = False
        user.tentatives_connexion = 0
        user.save()
        messages.success(request, f"Compte de {user.get_full_name()} débloqué.")

    return redirect("accounts:gestion_comptes")


@login_required
def profile_view(request):
    user = request.user

    if request.method == "POST":
        user.first_name = request.POST.get("first_name")
        user.last_name = request.POST.get("last_name")
        user.email = request.POST.get("email")
        user.telephone = request.POST.get("telephone")
        user.save()
        return redirect("accounts:profile")

    stats = {
        "actions": 25,
        "validations": 10,
        "refus": 5,
    }

    logs = []

    return render(request, "accounts/profile.html", {"stats": stats, "logs": logs})

"""
Service d'envoi d'emails OTP avec compte à rebours visuel
"""

from django.template.loader import render_to_string
from django.conf import settings
from accounts.email_utils import envoyer_email
from core.otp_service import OTPCode


def envoyer_email_otp(destinataire_email: str, otp: OTPCode, nom_utilisateur: str = "") -> bool:
    """
    Envoie un email avec le code OTP et la durée de validité.
    
    Args:
        destinataire_email: Email du destinataire
        otp: Objet OTPCode avec le code et la durée
        nom_utilisateur: Nom de l'utilisateur pour personnalisation
    
    Returns:
        bool: True si envoyé avec succès
    """
    # Calculer la durée en minutes
    duree_minutes = otp.time_remaining_seconds // 60
    
    # Contexte pour le template
    context = {
        'code': otp.code,
        'duree_minutes': duree_minutes,
        'duree_formatee': format_duree(duree_minutes),
        'nom_utilisateur': nom_utilisateur,
        'context': otp.context,
        'context_affiche': get_context_display(otp.context),
        'site_name': getattr(settings, 'SITE_NAME', 'Tunisie Telecom — Gestion Churn'),
    }
    
    # Rendre le template HTML
    html_content = render_to_string('emails/otp_code.html', context)
    
    # Sujet personnalisé selon le contexte
    sujet = f"🔐 Code de vérification — {context['context_affiche']}"
    
    # Envoyer l'email
    try:
        envoyer_email(destinataire_email, sujet, html_content)
        return True
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Échec envoi email OTP à {destinataire_email}: {e}")
        return False


def format_duree(minutes: int) -> str:
    """
    Formate la durée en texte lisible.
    
    Args:
        minutes: Nombre de minutes
    
    Returns:
        String formaté (ex: "10 minutes", "1 heure 30 minutes")
    """
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes > 1 else ''}"
    else:
        heures = minutes // 60
        mins_restantes = minutes % 60
        if mins_restantes == 0:
            return f"{heures} heure{'s' if heures > 1 else ''}"
        else:
            return f"{heures}h{mins_restantes:02d}"


def get_context_display(context: str) -> str:
    """
    Retourne le nom affichable du contexte.
    """
    contextes = {
        'default': 'Verification',
        'reset_password': 'Reinitialisation mot de passe',
        'validation_email': 'Validation email',
        'validation_telephone': 'Validation telephone',
    }
    return contextes.get(context, 'Vérification')

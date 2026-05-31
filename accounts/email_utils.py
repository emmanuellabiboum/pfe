from decouple import config
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import logging

logger = logging.getLogger(__name__)

def envoyer_email(destinataire, sujet, contenu):
    """
    Envoie un email via SendGrid.
    
    Args:
        destinataire: Email du destinataire
        sujet: Sujet de l'email
        contenu: Contenu HTML de l'email
        
    Returns:
        bool: True si envoyé avec succès
    """
    try:
        sg = SendGridAPIClient(config("SENDGRID_API_KEY"))
        msg = Mail(
            from_email=config("DEFAULT_FROM_EMAIL", default="churn@outlook.fr"),
            to_emails=destinataire,
            subject=sujet,
            html_content=contenu,
        )
        response = sg.send(msg)
        logger.info(f"Email envoyé à {destinataire} - Status: {response.status_code}")
        return True
    except Exception as e:
        logger.error(f"Erreur envoi email à {destinataire}: {e}")
        return False

import logging
from urllib.error import URLError
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from django.conf import settings
from decouple import config

logger = logging.getLogger(__name__)


def envoyer_email(destinataire, sujet, contenu):
    try:
        message = Mail(
            from_email=settings.DEFAULT_FROM_EMAIL,
            to_emails=destinataire,
            subject=sujet,
            html_content=contenu,
        )
        sg = SendGridAPIClient(config('SENDGRID_API_KEY'))
        response = sg.send(message)
        logger.info(f"Email envoyé avec succès à {destinataire} - Status: {response.status_code}")
    except URLError as e:
        logger.warning(f"Email non envoyé à {destinataire} — erreur réseau : {e}")
    except Exception as e:
        logger.warning(f"Email non envoyé à {destinataire} — erreur : {e}")

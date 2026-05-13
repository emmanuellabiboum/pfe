"""
Template tags pour afficher la durée et le temps restant
"""

from django import template
from django.utils.html import escape
from datetime import date, datetime, timedelta

register = template.Library()


@register.filter
def temps_restant_badge(recommandation):
    """
    Génère un badge HTML avec le temps restant et la couleur d'urgence.
    
    Usage: {{ rec|temps_restant_badge }}
    """
    if not recommandation.echeance:
        return '<span class="badge bg-secondary">Pas d\'échéance</span>'
    
    couleur = escape(recommandation.couleur_urgence)
    texte = escape(recommandation.temps_restant_affichage)
    
    # Ajouter une icône selon l'urgence (valeurs contrôlées, pas besoin d'escape)
    icones = {
        'critique': 'bi-exclamation-triangle-fill',
        'eleve': 'bi-clock-fill',
        'moyen': 'bi-hourglass-split',
        'faible': 'bi-check-circle-fill',
        'none': 'bi-dash-circle',
    }
    icone = icones.get(recommandation.urgence, 'bi-clock')
    
    return f'<span class="badge bg-{couleur}"><i class="bi {icone}"></i> {texte}</span>'


@register.filter
def temps_restant_texte(recommandation):
    """
    Retourne uniquement le texte du temps restant.
    
    Usage: {{ rec|temps_restant_texte }}
    """
    return recommandation.temps_restant_affichage if recommandation.echeance else ""


@register.filter
def couleur_urgence(recommandation):
    """
    Retourne la classe CSS de couleur d'urgence.
    
    Usage: class="alert-{{ rec|couleur_urgence }}"
    """
    return recommandation.couleur_urgence if recommandation.echeance else "secondary"


@register.filter
def est_en_retard(recommandation):
    """
    Retourne True si la recommandation est en retard.
    
    Usage: {% if rec|est_en_retard %}...{% endif %}
    """
    if not recommandation.echeance:
        return False
    return recommandation.temps_restant_jours < 0


@register.simple_tag
def countdown_timer(recommandation_id, echeance_date, statut):
    """
    Génère un compteur visuel JavaScript pour le temps restant.
    
    Usage: {% countdown_timer rec.id rec.echeance rec.statut %}
    """
    if not echeance_date or statut in ['completee', 'retiree', 'expiree']:
        return ""
    
    # Calculer le temps restant en millisecondes pour JavaScript
    today = date.today()
    delta = echeance_date - today
    jours_restants = delta.days
    
    # Déterminer la couleur
    if jours_restants < 0:
        couleur = "#dc2626"  # Rouge
        texte = f"En retard de {-jours_restants} jour(s)"
    elif jours_restants == 0:
        couleur = "#dc2626"  # Rouge
        texte = "Expire aujourd'hui"
    elif jours_restants <= 1:
        couleur = "#f59e0b"  # Orange
        texte = f"Expire dans {jours_restants} jour"
    elif jours_restants <= 3:
        couleur = "#f59e0b"  # Orange
        texte = f"{jours_restants} jours restants"
    elif jours_restants <= 7:
        couleur = "#3b82f6"  # Bleu
        texte = f"{jours_restants} jours restants"
    else:
        couleur = "#059669"  # Vert
        texte = f"{jours_restants} jours restants"
    
    return f'''
    <div class="countdown-timer" id="timer-{recommandation_id}" 
         style="color: {couleur}; font-weight: 600; font-size: 0.9rem;">
        <i class="bi bi-clock"></i> {texte}
    </div>
    '''


@register.filter
def duree_depuis_creation(date_creation):
    """
    Affiche la durée depuis la création (ex: "il y a 2h", "il y a 3j").
    """
    if not date_creation:
        return ""
    
    now = datetime.now()
    if isinstance(date_creation, date) and not isinstance(date_creation, datetime):
        date_creation = datetime.combine(date_creation, datetime.min.time())
    
    delta = now - date_creation
    
    if delta.days > 365:
        ans = delta.days // 365
        return f"il y a {ans} an{'s' if ans > 1 else ''}"
    elif delta.days > 30:
        mois = delta.days // 30
        return f"il y a {mois} mois"
    elif delta.days > 0:
        return f"il y a {delta.days} jour{'s' if delta.days > 1 else ''}"
    elif delta.seconds > 3600:
        heures = delta.seconds // 3600
        return f"il y a {heures}h"
    elif delta.seconds > 60:
        minutes = delta.seconds // 60
        return f"il y a {minutes}min"
    else:
        return "à l'instant"

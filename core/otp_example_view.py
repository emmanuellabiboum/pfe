"""
Exemple d'utilisation du système OTP avec envoi d'email et compteur visuel

Contextes disponibles:
- validation_telephone: 5 min, 4 chiffres (SMS)
- reset_password: 15 min, 6 caracteres
- validation_email: 30 min, 6 caracteres
- default: 5 min, 6 caracteres
"""

from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from core.otp_service import otp_service, generate_otp_for_user
from core.otp_email_service import envoyer_email_otp


@login_required
def demander_otp_reset_password(request):
    """
    Exemple: Demander un OTP pour reinitialisation de mot de passe.
    Duree: 15 minutes
    """
    if request.method == 'POST':
        otp = otp_service.generate(
            context='reset_password',
            user_id=request.user.id
        )
        
        email_envoye = envoyer_email_otp(
            destinataire_email=request.user.email,
            otp=otp,
            nom_utilisateur=request.user.get_full_name() or request.user.username
        )
        
        if email_envoye:
            messages.success(
                request, 
                f"Un code de verification a ete envoye a {request.user.email}. "
                f"Validite: 15 minutes."
            )
        else:
            messages.error(request, "Erreur lors de l'envoi de l'email.")
            return redirect('dashboard:accueil')
        
        request.session['otp_context'] = 'reset_password'
        
        return render(request, 'dashboard/otp_verification.html', {
            'otp_duration': otp.time_remaining_seconds,
            'context': 'reset_password',
            'context_affiche': 'Reinitialisation mot de passe',
        })
    
    return redirect('dashboard:accueil')


@login_required
def verifier_otp(request):
    """
    Vue pour valider le code OTP saisi par l'utilisateur.
    """
    if request.method == 'POST':
        code = request.POST.get('otp_code', '').strip().upper()
        context = request.session.get('otp_context', 'default')
        
        is_valid, message, otp_obj = otp_service.validate(code, context=context)
        
        if is_valid:
            messages.success(request, "Code verifie avec succes !")
            return redirect('dashboard:action_protegee')
        else:
            time_remaining = ""
            if otp_obj and not otp_obj.is_expired:
                time_remaining = f" (Temps restant: {otp_obj.time_remaining_formatted})"
            
            messages.error(request, f"{message}{time_remaining}")
            
            if otp_obj and otp_obj.is_expired:
                messages.info(request, "Le code a expire. Veuillez demander un nouveau code.")
            
            return redirect('dashboard:demander_otp_reset_password')
    
    return redirect('dashboard:accueil')


@login_required
@require_POST
def renvoyer_otp(request):
    """
    Vue AJAX pour renvoyer un nouveau code OTP.
    """
    context = request.session.get('otp_context', 'default')
    
    # Durees par contexte
    durees = {
        'reset_password': 15,
        'validation_email': 30,
        'validation_telephone': 5,
        'default': 5,
    }
    
    otp = otp_service.generate(
        context=context,
        user_id=request.user.id,
        custom_duration_minutes=durees.get(context, 5)
    )
    
    email_envoye = envoyer_email_otp(
        destinataire_email=request.user.email,
        otp=otp,
        nom_utilisateur=request.user.get_full_name() or request.user.username
    )
    
    if email_envoye:
        return JsonResponse({
            'success': True,
            'message': 'Nouveau code envoye !',
            'duration_seconds': otp.time_remaining_seconds,
            'duration_formatted': otp.time_remaining_formatted,
        })
    else:
        return JsonResponse({
            'success': False,
            'message': "Erreur lors de l'envoi."
        }, status=500)


@login_required
def otp_verification_page(request):
    """
    Page de verification OTP avec compteur visuel.
    """
    active_otp = otp_service.get_user_active_code(request.user.id)
    
    if not active_otp:
        messages.warning(request, "Aucun code actif.")
        return redirect('dashboard:accueil')
    
    return render(request, 'dashboard/otp_verification.html', {
        'otp_duration': active_otp.time_remaining_seconds,
        'context': active_otp.context,
        'context_affiche': active_otp.context.replace('_', ' ').title(),
    })

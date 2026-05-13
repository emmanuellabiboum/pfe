"""
Service OTP (One-Time Password) avec durée configurable
Génération, validation et expiration des codes à usage unique
"""

import random
import string
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import secrets
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class OTPStatus(Enum):
    """Statuts possibles d'un OTP"""
    ACTIVE = "active"
    USED = "used"
    EXPIRED = "expired"
    REVOKED = "revoked"


@dataclass
class OTPCode:
    """Représentation d'un code OTP"""
    code: str
    created_at: datetime
    expires_at: datetime
    status: OTPStatus = OTPStatus.ACTIVE
    used_at: Optional[datetime] = None
    attempts: int = 0
    max_attempts: int = 3
    context: str = ""  # Contexte: reset_password, validation_email, validation_telephone, default
    user_id: Optional[int] = None
    
    @property
    def is_expired(self) -> bool:
        """Vérifie si le code a expiré"""
        return datetime.now() > self.expires_at
    
    @property
    def is_valid(self) -> bool:
        """Vérifie si le code peut encore être utilisé"""
        return (
            self.status == OTPStatus.ACTIVE 
            and not self.is_expired 
            and self.attempts < self.max_attempts
        )
    
    @property
    def time_remaining_seconds(self) -> int:
        """Temps restant en secondes avant expiration"""
        if self.is_expired:
            return 0
        remaining = (self.expires_at - datetime.now()).total_seconds()
        return max(0, int(remaining))
    
    @property
    def time_remaining_formatted(self) -> str:
        """Temps restant formaté (MM:SS)"""
        seconds = self.time_remaining_seconds
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes:02d}:{secs:02d}"
    
    def to_dict(self) -> Dict:
        """Conversion en dictionnaire pour l'API"""
        return {
            'code': self.code,  # En production: ne pas exposer le code brut!
            'status': self.status.value,
            'is_valid': self.is_valid,
            'is_expired': self.is_expired,
            'time_remaining_seconds': self.time_remaining_seconds,
            'time_remaining_formatted': self.time_remaining_formatted,
            'expires_at': self.expires_at.isoformat(),
            'context': self.context,
            'attempts_remaining': self.max_attempts - self.attempts,
        }


class OTPService:
    """
    Service de gestion des OTP avec stockage en mémoire (cache).
    Pour la production, utiliser une base de données.
    """
    
    # Durées par défaut selon le contexte (en minutes)
    DEFAULT_DURATIONS = {
        'default': 5,
        'reset_password': 15,          # Réinitialisation de mot de passe
        'validation_email': 30,      # Validation d'email
        'validation_telephone': 5,   # Validation SMS
    }
    
    # Longueurs de code selon le contexte
    CODE_LENGTHS = {
        'default': 6,
        'validation_telephone': 4,   # SMS: code court
    }
    
    def __init__(self):
        # Stockage en mémoire: {code_hash: OTPCode}
        # ⚠️ AVERTISSEMENT PRODUCTION: Remplacer par une base de données pour multi-worker
        self._storage: Dict[str, OTPCode] = {}
        self._user_codes: Dict[int, str] = {}  # user_id -> code_hash
        
        # Rate limiting: {user_id: [timestamps]}
        self._rate_limit: Dict[int, list] = defaultdict(list)
        self._max_otp_per_hour = 5  # Max 5 OTP par heure par utilisateur
    
    def _check_rate_limit(self, user_id: int) -> Tuple[bool, str]:
        """
        Vérifie si l'utilisateur n'a pas dépassé la limite de génération d'OTP.
        
        Returns:
            (True, message) si autorisé, (False, raison) sinon
        """
        now = datetime.now()
        hour_ago = now - timedelta(hours=1)
        
        # Nettoyer les anciens timestamps
        self._rate_limit[user_id] = [
            ts for ts in self._rate_limit[user_id] if ts > hour_ago
        ]
        
        if len(self._rate_limit[user_id]) >= self._max_otp_per_hour:
            logger.warning(f"Rate limit atteint pour user_id={user_id}")
            return False, f"Limite atteinte: max {self._max_otp_per_hour} codes par heure"
        
        return True, "OK"
    
    def generate(
        self, 
        context: str = 'default',
        user_id: Optional[int] = None,
        custom_duration_minutes: Optional[int] = None,
        custom_length: Optional[int] = None
    ) -> OTPCode:
        """
        Génère un nouveau code OTP.
        
        Args:
            context: Type d'opération (affecte durée et longueur)
            user_id: ID utilisateur associé (optionnel)
            custom_duration_minutes: Durée personnalisée (override)
            custom_length: Longueur personnalisée (override)
        
        Returns:
            OTPCode généré
            
        Raises:
            RuntimeError: Si le rate limiting est atteint
        """
        # Vérifier le rate limiting si user_id fourni
        if user_id:
            allowed, reason = self._check_rate_limit(user_id)
            if not allowed:
                raise RuntimeError(reason)
            self._rate_limit[user_id].append(datetime.now())
        
        # Déterminer la durée
        duration = custom_duration_minutes or self.DEFAULT_DURATIONS.get(context, 5)
        
        # Déterminer la longueur
        length = custom_length or self.CODE_LENGTHS.get(context, 6)
        
        # Générer le code
        if context == 'validation_telephone':
            # Code numérique uniquement pour SMS
            code = ''.join(random.choices(string.digits, k=length))
        else:
            # Code alphanumérique pour autres usages
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
        
        # Créer l'objet OTP
        now = datetime.now()
        otp = OTPCode(
            code=code,
            created_at=now,
            expires_at=now + timedelta(minutes=duration),
            context=context,
            user_id=user_id,
            max_attempts=3
        )
        
        # Stocker (avec hash du code pour la clé)
        code_hash = self._hash_code(code)
        self._storage[code_hash] = otp
        
        if user_id:
            # Révoquer l'ancien code de l'utilisateur s'il existe
            old_hash = self._user_codes.get(user_id)
            if old_hash and old_hash in self._storage:
                self._storage[old_hash].status = OTPStatus.REVOKED
            self._user_codes[user_id] = code_hash
        
        return otp
    
    def validate(self, code: str, context: Optional[str] = None) -> Tuple[bool, str, Optional[OTPCode]]:
        """
        Valide un code OTP.
        
        Args:
            code: Code à valider
            context: Contexte attendu (optionnel, pour validation stricte)
        
        Returns:
            Tuple: (is_valid, message, otp_object)
        """
        code_hash = self._hash_code(code)
        
        if code_hash not in self._storage:
            logger.warning(f"Tentative de validation avec code inexistant: {code[:3]}...")
            return False, "Code invalide", None
        
        otp = self._storage[code_hash]
        
        # Vérifier le contexte si spécifié
        if context and otp.context != context:
            return False, "Code invalide pour ce contexte", None
        
        # Vérifier les tentatives
        otp.attempts += 1
        if otp.attempts >= otp.max_attempts:
            otp.status = OTPStatus.REVOKED
            return False, "Trop de tentatives. Code révoqué.", otp
        
        # Vérifier l'expiration
        if otp.is_expired:
            otp.status = OTPStatus.EXPIRED
            return False, "Code expiré", otp
        
        # Vérifier si déjà utilisé
        if otp.status == OTPStatus.USED:
            return False, "Code déjà utilisé", otp
        
        if otp.status == OTPStatus.REVOKED:
            return False, "Code révoqué", otp
        
        # Succès!
        otp.status = OTPStatus.USED
        otp.used_at = datetime.now()
        logger.info(f"OTP validé avec succès pour user_id={otp.user_id}, context={otp.context}")
        return True, "Code validé avec succès", otp
    
    def get_status(self, code: str) -> Optional[Dict]:
        """
        Récupère le statut d'un code sans le valider.
        
        Returns:
            Dict avec statut et temps restant, ou None si code inconnu
        """
        code_hash = self._hash_code(code)
        
        if code_hash not in self._storage:
            return None
        
        otp = self._storage[code_hash]
        
        # Mettre à jour le statut si expiré
        if otp.is_expired and otp.status == OTPStatus.ACTIVE:
            otp.status = OTPStatus.EXPIRED
        
        return otp.to_dict()
    
    def get_time_remaining(self, code: str) -> Optional[int]:
        """
        Récupère le temps restant en secondes pour un code.
        
        Returns:
            Secondes restantes, ou None si code inconnu
        """
        code_hash = self._hash_code(code)
        
        if code_hash not in self._storage:
            return None
        
        return self._storage[code_hash].time_remaining_seconds
    
    def revoke(self, code: str) -> bool:
        """Révoque un code active"""
        code_hash = self._hash_code(code)
        
        if code_hash in self._storage:
            self._storage[code_hash].status = OTPStatus.REVOKED
            return True
        return False
    
    def cleanup_expired(self) -> int:
        """
        Nettoie les codes expirés du stockage.
        
        Returns:
            Nombre de codes supprimés
        """
        to_remove = []
        
        for code_hash, otp in self._storage.items():
            # Supprimer les codes expirés depuis plus de 24h
            if otp.is_expired and (datetime.now() - otp.expires_at).total_seconds() > 86400:
                to_remove.append(code_hash)
            # Supprimer les codes utilisés depuis plus de 1h
            elif otp.status == OTPStatus.USED and otp.used_at:
                if (datetime.now() - otp.used_at).total_seconds() > 3600:
                    to_remove.append(code_hash)
        
        for code_hash in to_remove:
            del self._storage[code_hash]
        
        return len(to_remove)
    
    def _hash_code(self, code: str) -> str:
        """Hash le code pour le stockage sécurisé"""
        return hashlib.sha256(code.encode()).hexdigest()[:32]
    
    def get_user_active_code(self, user_id: int) -> Optional[OTPCode]:
        """Récupère le code actif d'un utilisateur"""
        code_hash = self._user_codes.get(user_id)
        if code_hash and code_hash in self._storage:
            otp = self._storage[code_hash]
            if otp.is_valid:
                return otp
        return None


# Instance singleton du service
otp_service = OTPService()


# Fonctions utilitaires pour l'API Django

def generate_otp_for_user(
    user_id: int, 
    context: str = 'default',
    duration_minutes: Optional[int] = None
) -> Tuple[str, int]:
    """
    Génère un OTP pour un utilisateur.
    
    Returns:
        Tuple: (code_clair, duree_secondes)
    """
    otp = otp_service.generate(
        context=context,
        user_id=user_id,
        custom_duration_minutes=duration_minutes
    )
    return otp.code, otp.time_remaining_seconds


def validate_otp_code(code: str, context: Optional[str] = None) -> Dict:
    """
    Valide un code OTP (fonction utilitaire pour les vues).
    
    Returns:
        Dict avec succès/échec et détails
    """
    is_valid, message, otp = otp_service.validate(code, context)
    
    result = {
        'valid': is_valid,
        'message': message,
    }
    
    if otp:
        result['context'] = otp.context
        result['expired'] = otp.is_expired
        if not is_valid and not otp.is_expired:
            result['time_remaining'] = otp.time_remaining_formatted
            result['attempts_remaining'] = otp.max_attempts - otp.attempts
    
    return result


def get_otp_time_remaining(code: str) -> Optional[Dict]:
    """
    Récupère le temps restant pour un code.
    
    Usage dans les templates/vues pour afficher le compte à rebours.
    """
    status = otp_service.get_status(code)
    
    if not status:
        return None
    
    return {
        'seconds': status['time_remaining_seconds'],
        'formatted': status['time_remaining_formatted'],
        'is_valid': status['is_valid'],
        'is_expired': status['is_expired'],
        'attempts_remaining': status['attempts_remaining'],
    }

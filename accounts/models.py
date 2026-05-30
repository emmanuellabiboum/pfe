from django.contrib.auth.models import AbstractUser, UserManager as BaseUserManager
from django.db import models
from core.models import Agence, Ville


class UserManager(BaseUserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'admin')
        extra_fields.setdefault('statut', 'actif')
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self._create_user(username, email, password, **extra_fields)


class User(AbstractUser):
    objects = UserManager()
    ROLES = [
        ("super_admin", "Super Administrateur"),
        ("admin", "Administrateur Ville"),
        ("chef_agence", "Chef d'agence"),
        ("agent_marketing", "Agent Marketing"),
        ("agent_commercial", "Agent Commercial"),
    ]

    STATUTS = [
        ("en_attente", "En attente de validation"),
        ("actif", "Actif"),
        ("suspendu", "Suspendu"),
    ]

    role = models.CharField(max_length=20, choices=ROLES)
    ville = models.ForeignKey(Ville, on_delete=models.PROTECT, null=True, blank=True, related_name="admins")
    agence = models.ForeignKey(Agence, on_delete=models.PROTECT, null=True, blank=True, related_name="employes")
    statut = models.CharField(max_length=20, choices=STATUTS, default="en_attente")
    telephone = models.CharField(max_length=20, blank=True)
    date_demande = models.DateTimeField(auto_now_add=True)
    date_validation = models.DateTimeField(null=True, blank=True)
    tentatives_connexion = models.IntegerField(default=0)
    est_bloque = models.BooleanField(default=False)
    valide_par = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="comptes_valides",
    )

    def save(self, *args, **kwargs):
        if self.is_superuser or self.role in ["admin", "super_admin"]:
            self.statut = "actif"
            if self.is_superuser and not self.role:
                self.role = "super_admin"
        super().save(*args, **kwargs)

    def __str__(self):
        if self.role in ["admin", "super_admin"] and self.ville:
            return f"{self.get_full_name()} ({self.get_role_display()} {self.ville.nom})"
        elif self.agence:
            return f"{self.get_full_name()} ({self.get_role_display()}) - {self.agence}"
        return f"{self.get_full_name()} ({self.get_role_display()})"

    def get_validation_scope(self):
        if self.role in ["admin", "super_admin"]:
            return f"ville:{self.ville_id}"
        elif self.role == "chef_agence":
            return f"agence:{self.agence_id}"
        return None

    def clean(self):
        from django.core.exceptions import ValidationError
        # Admin et Super Admin ne peuvent pas avoir d'agence (ils gèrent la ville entière)
        if self.role in ["admin", "super_admin"] and self.agence:
            raise ValidationError({
                'agence': 'Un administrateur de ville ne peut pas être associé à une agence spécifique.'
            })
        # Les rôles d'agence (chef, agents) doivent avoir une agence
        if self.role in ["chef_agence", "agent_marketing", "agent_commercial"] and not self.agence:
            raise ValidationError({
                'agence': 'Ce rôle nécessite une agence.'
            })
        
        # Limite de 3 utilisateurs par agence
        if self.agence:
            nb_employes = User.objects.filter(agence=self.agence).exclude(pk=self.pk).count()
            if nb_employes >= 3:
                raise ValidationError({
                    'agence': f"L'agence {self.agence.nom} a déjà atteint la limite maximale de 3 employés."
                })
        super().clean()

    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"


class OTPCode(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    code = models.CharField(max_length=6)
    expire_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"OTP {self.user.username} - {self.code}"


class LoginActivity(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)


class AdminVille(models.Model):
    """
    Modèle séparé pour les administrateurs de ville.
    Permet de gérer les admins sans affecter la logique ville+agence des agents.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='admin_ville',
        limit_choices_to={'role__in': ['admin', 'super_admin']}
    )
    ville = models.ForeignKey(
        Ville,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='administrateurs'
    )
    date_nomination = models.DateTimeField(auto_now_add=True)
    actif = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.get_full_name()} - Admin {self.ville.nom if self.ville else 'sans ville'}"

    class Meta:
        verbose_name = "Administrateur de ville"
        verbose_name_plural = "Administrateurs de ville"
        permissions = [
            ('valider_chef_agence', 'Peut valider les chefs d\'agence de sa ville'),
            ('gerer_utilisateurs_ville', 'Peut gérer les utilisateurs de sa ville'),
        ]

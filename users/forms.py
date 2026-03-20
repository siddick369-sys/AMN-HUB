"""
Formulaires — Module Users, AMN Employee Hub.
Tous les labels et messages utilisent gettext_lazy pour le bilinguisme FR/EN.
"""

from django import forms
from django.contrib.auth import password_validation
from django.utils.translation import gettext_lazy as _

from .models import Employee, PreferredLanguage


# ─── Style Tailwind commun pour les inputs ───────────────────────────────────
INPUT_CLASSES = (
    'w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl '
    'text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 '
    'focus:ring-navy-500 focus:border-navy-400 transition-all duration-200'
)

SELECT_CLASSES = (
    'w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl '
    'text-slate-800 focus:outline-none focus:ring-2 focus:ring-navy-500 '
    'focus:border-navy-400 transition-all duration-200'
)


class RegistrationForm(forms.ModelForm):
    """Formulaire d'inscription d'un nouvel employé."""

    password1 = forms.CharField(
        label=_('Mot de passe'),
        widget=forms.PasswordInput(attrs={
            'class': INPUT_CLASSES,
            'placeholder': _('Minimum 8 caractères'),
            'autocomplete': 'new-password',
        })
    )

    password2 = forms.CharField(
        label=_('Confirmer le mot de passe'),
        widget=forms.PasswordInput(attrs={
            'class': INPUT_CLASSES,
            'placeholder': _('Répétez votre mot de passe'),
            'autocomplete': 'new-password',
        })
    )

    class Meta:
        model = Employee
        fields = [
            'first_name', 'last_name', 'username', 'email',
            'department', 'country', 'preferred_language',
        ]
        labels = {
            'first_name':          _('Prénom'),
            'last_name':           _('Nom'),
            'username':            _("Nom d'utilisateur"),
            'email':               _('Adresse email professionnelle'),
            'department':          _('Département'),
            'country':             _('Pays'),
            'preferred_language':  _('Langue préférée'),
        }
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': INPUT_CLASSES,
                'placeholder': _('Votre prénom'),
                'autofocus': True,
            }),
            'last_name': forms.TextInput(attrs={
                'class': INPUT_CLASSES,
                'placeholder': _('Votre nom de famille'),
            }),
            'username': forms.TextInput(attrs={
                'class': INPUT_CLASSES,
                'placeholder': _('ex: j.dupont'),
                'autocomplete': 'username',
            }),
            'email': forms.EmailInput(attrs={
                'class': INPUT_CLASSES,
                'placeholder': _('prenom.nom@africamobilenetworks.com'),
                'autocomplete': 'email',
            }),
            'department': forms.Select(attrs={'class': SELECT_CLASSES}),
            'country':    forms.Select(attrs={'class': SELECT_CLASSES}),
            'preferred_language': forms.Select(attrs={'class': SELECT_CLASSES}),
        }

    def clean_password1(self):
        password = self.cleaned_data.get('password1')
        if password:
            password_validation.validate_password(password)
        return password

    def clean_password2(self):
        p1 = self.cleaned_data.get('password1')
        p2 = self.cleaned_data.get('password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError(_('Les mots de passe ne correspondent pas.'))
        return p2

    def clean_email(self):
        email = self.cleaned_data.get('email', '').lower().strip()
        if Employee.objects.filter(email=email).exists():
            raise forms.ValidationError(_('Cette adresse email est déjà utilisée.'))
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        user.is_verified = False
        if commit:
            user.save()
        return user


class LoginForm(forms.Form):
    """Formulaire de connexion."""

    username = forms.CharField(
        label=_("Nom d'utilisateur ou email"),
        widget=forms.TextInput(attrs={
            'class': INPUT_CLASSES,
            'placeholder': _("Nom d'utilisateur ou email"),
            'autofocus': True,
            'autocomplete': 'username',
        })
    )

    password = forms.CharField(
        label=_('Mot de passe'),
        widget=forms.PasswordInput(attrs={
            'class': INPUT_CLASSES,
            'placeholder': _('Votre mot de passe'),
            'autocomplete': 'current-password',
        })
    )

    remember_me = forms.BooleanField(
        label=_('Se souvenir de moi'),
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'w-4 h-4 text-navy-600 bg-white border-slate-300 rounded focus:ring-navy-500'
        })
    )


class VerificationCodeForm(forms.Form):
    """Formulaire de saisie du code OTP de vérification email."""

    code = forms.CharField(
        label=_('Code de vérification'),
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            'class': (
                'w-full text-center text-3xl font-mono tracking-[0.5em] px-4 py-4 '
                'bg-white/5 border border-white/10 rounded-2xl text-white '
                'placeholder-white/20 focus:outline-none focus:ring-2 '
                'focus:ring-blue-500 transition-all duration-200'
            ),
            'placeholder': '000000',
            'autofocus': True,
            'autocomplete': 'one-time-code',
            'inputmode': 'numeric',
            'pattern': '[0-9]{6}',
            'maxlength': '6',
        })
    )

    def clean_code(self):
        code = self.cleaned_data.get('code', '').strip()
        if not code.isdigit():
            raise forms.ValidationError(_('Le code doit contenir uniquement des chiffres.'))
        return code


class PasswordResetRequestForm(forms.Form):
    """Formulaire de demande de réinitialisation du mot de passe."""

    email = forms.EmailField(
        label=_('Adresse email'),
        widget=forms.EmailInput(attrs={
            'class': INPUT_CLASSES,
            'placeholder': _('Votre adresse email professionnelle'),
            'autofocus': True,
            'autocomplete': 'email',
        })
    )


class PasswordResetConfirmForm(forms.Form):
    """Formulaire de saisie du nouveau mot de passe."""

    password1 = forms.CharField(
        label=_('Nouveau mot de passe'),
        widget=forms.PasswordInput(attrs={
            'class': INPUT_CLASSES,
            'placeholder': _('Minimum 8 caractères'),
            'autofocus': True,
            'autocomplete': 'new-password',
        })
    )

    password2 = forms.CharField(
        label=_('Confirmer le nouveau mot de passe'),
        widget=forms.PasswordInput(attrs={
            'class': INPUT_CLASSES,
            'placeholder': _('Répétez le nouveau mot de passe'),
            'autocomplete': 'new-password',
        })
    )

    def clean_password1(self):
        password = self.cleaned_data.get('password1')
        if password:
            password_validation.validate_password(password)
        return password

    def clean_password2(self):
        p1 = self.cleaned_data.get('password1')
        p2 = self.cleaned_data.get('password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError(_('Les mots de passe ne correspondent pas.'))
        return p2


class ProfileUpdateForm(forms.ModelForm):
    """Formulaire de mise à jour du profil employé."""

    class Meta:
        model = Employee
        fields = [
            'first_name', 'last_name', 'job_title',
            'phone_number', 'department', 'country',
            'preferred_language', 'avatar',
        ]
        labels = {
            'first_name':         _('Prénom'),
            'last_name':          _('Nom'),
            'job_title':          _('Poste / Titre'),
            'phone_number':       _('Téléphone'),
            'department':         _('Département'),
            'country':            _('Pays'),
            'preferred_language': _('Langue préférée'),
            'avatar':             _('Photo de profil'),
        }
        widgets = {
            'first_name':    forms.TextInput(attrs={'class': INPUT_CLASSES}),
            'last_name':     forms.TextInput(attrs={'class': INPUT_CLASSES}),
            'job_title':     forms.TextInput(attrs={'class': INPUT_CLASSES}),
            'phone_number':  forms.TextInput(attrs={'class': INPUT_CLASSES}),
            'department':    forms.Select(attrs={'class': SELECT_CLASSES}),
            'country':       forms.Select(attrs={'class': SELECT_CLASSES}),
            'preferred_language': forms.Select(attrs={'class': SELECT_CLASSES}),
            'avatar':        forms.ClearableFileInput(attrs={
                'class': 'hidden',
                'id': 'avatar-upload',
                'accept': 'image/*',
            }),
        }

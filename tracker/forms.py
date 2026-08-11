from django import forms
from django.db import transaction
from django.utils import timezone

from allauth.account.forms import SignupForm

from .models import InviteCode, InviteRedemption, SiteConfiguration


class InviteSignupForm(SignupForm):
    invite_code = forms.CharField(
        label='Invite code',
        max_length=160,
        strip=True,
        widget=forms.TextInput(attrs={
            'autocomplete': 'one-time-code',
            'placeholder': 'Invite code',
        }),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.invite_required = not SiteConfiguration.registration_is_open()
        # Keep browser and server feedback consistent across normal and
        # Passkey signup. Conditional validation lives in clean_invite_code().
        self.fields['invite_code'].required = False
        if not self.invite_required:
            self.fields['invite_code'].label = 'Invite code (optional)'
            self.fields['invite_code'].widget.attrs['placeholder'] = 'Optional while registration is open'

    def clean_invite_code(self):
        raw_code = self.cleaned_data.get('invite_code', '').strip()
        if not raw_code:
            if self.invite_required:
                raise forms.ValidationError('Enter an invite code to create an account.')
            return ''
        invite = InviteCode.objects.filter(code_digest=InviteCode.digest(raw_code)).first()
        if invite is None or not invite.usable:
            raise forms.ValidationError('This invite code is invalid, expired, or already used.')
        return raw_code

    def save(self, request):
        with transaction.atomic():
            raw_code = self.cleaned_data.get('invite_code', '').strip()
            if not raw_code:
                if not SiteConfiguration.registration_is_open():
                    raise forms.ValidationError('An invite code is required while registration is closed.')
                return super().save(request)
            digest = InviteCode.digest(raw_code)
            invite = InviteCode.objects.select_for_update().filter(code_digest=digest).first()
            if invite is None or not invite.usable:
                raise forms.ValidationError('This invite code is no longer available.')
            user = super().save(request)
            invite.use_count += 1
            invite.last_used_at = timezone.now()
            if invite.use_count >= invite.max_uses:
                invite.is_active = False
            invite.save(update_fields=('use_count', 'last_used_at', 'is_active'))
            InviteRedemption.objects.create(invite=invite, user=user)
            return user


class AdminInviteCodeForm(forms.Form):
    name = forms.CharField(label='Label', max_length=120)
    max_uses = forms.IntegerField(label='Maximum uses', min_value=1, max_value=100, initial=1)
    expires_at = forms.DateTimeField(
        label='Expires at',
        required=False,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
    )

    def clean_expires_at(self):
        value = self.cleaned_data.get('expires_at')
        if value and value <= timezone.now():
            raise forms.ValidationError('Expiry must be in the future.')
        return value


class RegistrationPolicyForm(forms.Form):
    registration_open = forms.BooleanField(
        label='Open registration',
        required=False,
        help_text='When enabled, anyone can create an account without an invite code.',
    )
    math_visualization_enabled = forms.BooleanField(
        label='Enable math visualization',
        required=False,
        help_text='Show formula launch buttons and allow the on-demand visualization window.',
    )


class LoginRateLimitResetForm(forms.Form):
    network_address = forms.GenericIPAddressField(
        label='Network address',
        required=False,
        help_text='Leave blank to use the network address of this admin session.',
        widget=forms.TextInput(attrs={'placeholder': '203.0.113.10'}),
    )


class ContactForm(forms.Form):
    name = forms.CharField(label='Your name', max_length=120)
    reply_email = forms.EmailField(label='Your email', max_length=254)
    message = forms.CharField(
        label='Message',
        min_length=10,
        max_length=4000,
        widget=forms.Textarea(attrs={'rows': 8}),
    )
    website = forms.CharField(
        required=False,
        label='',
        widget=forms.TextInput(attrs={
            'autocomplete': 'off',
            'tabindex': '-1',
            'aria-hidden': 'true',
        }),
    )

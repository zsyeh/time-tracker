from django import forms
from django.db import transaction
from django.utils import timezone

from allauth.account.forms import SignupForm

from .models import InviteCode, InviteRedemption


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

    def clean_invite_code(self):
        raw_code = self.cleaned_data['invite_code'].strip()
        invite = InviteCode.objects.filter(code_digest=InviteCode.digest(raw_code)).first()
        if invite is None or not invite.usable:
            raise forms.ValidationError('This invite code is invalid, expired, or already used.')
        return raw_code

    def save(self, request):
        with transaction.atomic():
            digest = InviteCode.digest(self.cleaned_data['invite_code'])
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

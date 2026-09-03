from allauth.account.adapter import DefaultAccountAdapter


class PrivateAccountAdapter(DefaultAccountAdapter):
    """Expose signup while requiring the server-side invite form."""

    def is_open_for_signup(self, request):
        return True

    def clean_password(self, password, user=None):
        """Accept short passwords while steering users toward Passkeys in the UI.

        Required form fields still reject an empty password and Django Admin
        keeps its normal validators. This only changes allauth account flows.
        """
        return password

    def get_login_stages(self):
        """Offer password and Passkey as independent, single-step login methods.

        django-allauth models WebAuthn credentials inside its MFA application.
        Its default stages consequently ask for a Passkey after a successful
        password login whenever the account has one.  This instance treats a
        password *or* a passwordless Passkey as a complete credential instead.
        The Passkey signup stage remains available for Passkey-only accounts.
        """
        second_factor_stages = {
            'allauth.mfa.stages.AuthenticateStage',
            'allauth.mfa.stages.TrustStage',
        }
        stages = [
            stage for stage in super().get_login_stages()
            if stage not in second_factor_stages
        ]
        passkey_stage = 'allauth.mfa.webauthn.stages.PasskeySignupStage'
        if passkey_stage not in stages:
            stages.append(passkey_stage)
        return stages

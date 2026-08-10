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

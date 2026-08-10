from allauth.account.adapter import DefaultAccountAdapter


class PrivateAccountAdapter(DefaultAccountAdapter):
    """Expose signup while requiring the server-side invite form."""

    def is_open_for_signup(self, request):
        return True

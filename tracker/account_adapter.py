from allauth.account.adapter import DefaultAccountAdapter


class PrivateAccountAdapter(DefaultAccountAdapter):
    """Keep this personal system invite/admin provisioned, not public signup."""

    def is_open_for_signup(self, request):
        return False

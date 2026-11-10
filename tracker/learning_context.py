"""Optional account affinity for restored browser state; authentication is unchanged."""
from django.http import JsonResponse

class LearningAccountContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    def __call__(self, request):
        expected = request.headers.get('X-Learning-User-ID')
        if (expected and request.path.startswith('/api/') and request.path != '/api/auth/session/'
                and request.user.is_authenticated and expected != str(request.user.pk)):
            response = JsonResponse({'detail': 'Account changed. Reload before using saved learning state.'}, status=409)
            response['Cache-Control'] = 'private, no-store'
            return response
        return self.get_response(request)

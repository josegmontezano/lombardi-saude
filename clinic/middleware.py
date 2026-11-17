from django.shortcuts import redirect


class MustChangePasswordMiddleware:
    """Master administrators cannot use the system before rotating bootstrap passwords."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        path = request.path_info
        if (user and user.is_authenticated and getattr(user, 'must_change_password', False)
            and not path.startswith('/static/')
            and not path.startswith('/gestao/password_change/') and not path.startswith('/gestao/logout/')):
            return redirect('/gestao/password_change/')
        return self.get_response(request)

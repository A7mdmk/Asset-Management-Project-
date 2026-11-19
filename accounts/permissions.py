
from functools import wraps

from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required


def has_role(user, role):
    if not user.is_authenticated or not user.is_active:
        return False

    return user.groups.filter(name=role).exists()


def role_required(*roles):
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if request.user.is_superuser or any(
                has_role(request.user, role) for role in roles
            ):
                return view_func(request, *args, **kwargs)

            raise PermissionDenied

        return wrapped

    return decorator

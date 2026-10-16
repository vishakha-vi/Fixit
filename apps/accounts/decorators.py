from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def feature_required(*codes):
    """Allow the view when the logged-in user has at least one of the given features."""

    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not any(request.user.has_feature(code) for code in codes):
                raise PermissionDenied("You do not have access to this feature.")
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def admin_required(view_func):
    """Only users with the Admin role (or superusers) may use the admin portal."""

    @login_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_admin_role():
            raise PermissionDenied("Only administrators can open the admin portal.")
        return view_func(request, *args, **kwargs)

    return wrapper

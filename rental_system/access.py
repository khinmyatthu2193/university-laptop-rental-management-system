from functools import wraps

from django.contrib import messages
from django.http import HttpResponseForbidden
from django.shortcuts import redirect

from .models import ManagementStaff


SAFE_METHODS = {'GET', 'HEAD', 'OPTIONS'}
WRITE_ROLES = {'SystemAdmin', 'Admin'}


def _active_management_staff(request):
    if not request.user.is_authenticated or not request.user.is_active:
        return None

    try:
        staff = request.user.management_profile
    except ManagementStaff.DoesNotExist:
        return None

    if staff.status != 'Active':
        return None
    return staff


def staff_access(view_func=None, *, allow_self_service_write=False):
    """Require an active management account and protect non-safe operations."""

    def decorator(func):
        @wraps(func)
        def wrapped(request, *args, **kwargs):
            staff = _active_management_staff(request)
            if staff is None:
                messages.error(request, 'Please sign in with an active account.')
                return redirect('rental_system:login')

            request.management_staff = staff
            request.session['staff_id'] = staff.id

            is_write = request.method not in SAFE_METHODS
            if is_write and not allow_self_service_write and staff.role not in WRITE_ROLES:
                return HttpResponseForbidden('Your account has read-only access.')
            return func(request, *args, **kwargs)

        return wrapped

    if view_func is None:
        return decorator
    return decorator(view_func)


def system_admin_required(view_func):
    @wraps(view_func)
    @staff_access
    def wrapped(request, *args, **kwargs):
        if request.management_staff.role != 'SystemAdmin':
            return HttpResponseForbidden('System administrator access is required.')
        return view_func(request, *args, **kwargs)

    return wrapped

from functools import wraps

from django.contrib import messages
from django.http import HttpResponseForbidden
from django.shortcuts import redirect

from .models import ManagementStaff


SAFE_METHODS = {'GET', 'HEAD', 'OPTIONS'}

PERMISSION_GROUPS = (
    ('dashboard', 'Dashboard', 'View the dashboard and summary information.', False),
    ('students', 'Student records', 'View or maintain student records and imports.', True),
    ('staff_records', 'University staff records', 'View or maintain laptop-recipient staff records.', True),
    ('inventory', 'Laptop inventory', 'View or maintain laptops and inventory imports.', True),
    ('assignments', 'Laptop assignments', 'View or create laptop assignments.', True),
    ('returns', 'Laptop returns', 'View or process laptop returns.', True),
    ('issues', 'Issues and repairs', 'View or update damage and repair records.', True),
    ('audit_logs', 'Audit logs', 'View the system activity history.', False),
    ('system_preferences', 'System preferences', 'View and change system-wide preferences.', True),
)

ALL_PERMISSION_CODES = tuple(
    code
    for key, _label, _description, can_manage in PERMISSION_GROUPS
    for code in ([f'{key}.view', f'{key}.manage'] if can_manage else [f'{key}.view'])
)

PERMISSION_LANDING_PAGES = (
    ('dashboard.view', 'rental_system:home'),
    ('students.view', 'rental_system:student_list'),
    ('staff_records.view', 'rental_system:staff_list'),
    ('inventory.view', 'rental_system:inventory_list'),
    ('assignments.view', 'rental_system:assigned_laptop_list'),
    ('returns.view', 'rental_system:return_laptop_list'),
    ('issues.view', 'rental_system:issue_list'),
    ('audit_logs.view', 'rental_system:audit_logs'),
    ('system_preferences.view', 'rental_system:system_preferences'),
)


def landing_page_for(staff):
    for permission, route_name in PERMISSION_LANDING_PAGES:
        if staff.has_permission(permission):
            return route_name
    return 'rental_system:profile_settings'


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

            return func(request, *args, **kwargs)

        return wrapped

    if view_func is None:
        return decorator
    return decorator(view_func)


def permission_required(view_permission, manage_permission=None):
    """Require a module permission, using manage_permission for unsafe requests."""
    def decorator(view_func):
        @wraps(view_func)
        @staff_access
        def wrapped(request, *args, **kwargs):
            permission = view_permission
            if request.method not in SAFE_METHODS:
                permission = manage_permission or view_permission
            if not request.management_staff.has_permission(permission):
                return HttpResponseForbidden('Your account is not authorized for this area.')
            return view_func(request, *args, **kwargs)
        return wrapped
    return decorator


def system_admin_required(view_func):
    @wraps(view_func)
    @staff_access
    def wrapped(request, *args, **kwargs):
        staff = request.management_staff
        owner_exists = ManagementStaff.objects.filter(username__iexact='daw_moe_thida').exists()
        if not staff.is_account_owner and (owner_exists or staff.role != 'SystemAdmin'):
            return HttpResponseForbidden('Only Daw Moe Thida can manage staff accounts and authorization.')
        return view_func(request, *args, **kwargs)

    return wrapped

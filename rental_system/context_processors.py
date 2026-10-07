from rental_system.models import Laptop, ManagementStaff

def available_laptops(request):
    management_staff = None
    if request.user.is_authenticated:
        try:
            management_staff = request.user.management_profile
        except (AttributeError, ManagementStaff.DoesNotExist):
            pass
    access = {}
    if management_staff:
        for module in ('dashboard', 'students', 'staff_records', 'inventory', 'assignments', 'returns', 'issues', 'audit_logs', 'system_preferences'):
            access[module] = {
                'view': management_staff.has_permission(f'{module}.view'),
                'manage': management_staff.has_permission(f'{module}.manage'),
            }
    return {
        'available_laptops': Laptop.objects.filter(status='Available').count(),
        'management_staff': management_staff,
        'access': access,
    }

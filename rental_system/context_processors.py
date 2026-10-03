from rental_system.models import Laptop, ManagementStaff

def available_laptops(request):
    management_staff = None
    if request.user.is_authenticated:
        try:
            management_staff = request.user.management_profile
        except (AttributeError, ManagementStaff.DoesNotExist):
            pass
    return {
        'available_laptops': Laptop.objects.filter(status='Available').count(),
        'management_staff': management_staff,
    }

from rental_system.models import Laptop

def available_laptops(request):
    return {
        'available_laptops': Laptop.objects.filter(status='Available').count()
    }
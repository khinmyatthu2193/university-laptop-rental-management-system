from django.urls import path
from django.views.decorators.http import require_POST

from . import views
from .access import staff_access, system_admin_required

app_name = 'rental_system'

urlpatterns = [
    # Home / Dashboard
    path('', staff_access(views.home_view), name='home'),
    path('login/', views.login_view, name='login'),
    path('signin/', views.signin_view, name='signin'),
    path('logout/', staff_access(require_POST(views.logout_view), allow_self_service_write=True), name='logout'),
    
    #KMT's Code for Student Management
    path("students/", staff_access(views.student_list), name="student_list"),
    path("students/create/", staff_access(views.student_create), name="student_create"),
    path("students/<int:pk>/edit/", staff_access(views.student_update), name="student_update"),
    path('students/import/', staff_access(views.import_students_excel), name='import_students'),
    #End of KMT's Code
    
    path('staffs/', staff_access(views.staff_list), name='staff_list'),
    path('staffs/create/', staff_access(views.staff_create), name='staff_create'),
    path('staffs/<int:pk>/edit/', staff_access(views.staff_update), name='staff_update'),
    path("staff/import/", staff_access(views.import_staff_excel), name="import_staff"),
    
    #SAL's Code for Laptop Management
    path("inventory/", staff_access(views.inventory_list), name="inventory_list"),
    path("inventory/create/", staff_access(views.laptop_create), name="laptop_create"),
    path("inventory/<int:pk>/edit/", staff_access(views.laptop_update), name="laptop_update"),
    path('assignments/', staff_access(views.assigned_laptop_list), name='assigned_laptop_list'),
    path('returns/', staff_access(views.return_laptop_list), name='return_laptop_list'),
    path('issues/', staff_access(views.issue_list), name='issue_list'),
    #End of SAL's Code
    path("inventory/import/", staff_access(views.import_laptops_excel), name="import_laptops"),

# Quick Assign
    path('quick-assign/', staff_access(views.quick_assign), name='quick_assign'),
    
    # Admin Settings
    path('profile-settings/', staff_access(views.profile_settings), name='profile_settings'),
    path('account-settings/', staff_access(views.account_settings), name='account_settings'),
    path('system-preferences/', staff_access(views.system_preferences), name='system_preferences'),
    path('audit-logs/', staff_access(views.audit_logs), name='audit_logs'),
    path('update-profile/', staff_access(views.update_profile, allow_self_service_write=True), name='update_profile'),
    path('change-password/', staff_access(views.change_password, allow_self_service_write=True), name='change_password'),
    path('deactivate-account/', staff_access(require_POST(views.deactivate_account), allow_self_service_write=True), name='deactivate_account'),
    path('save-preferences/', staff_access(views.save_preferences), name='save_preferences'),
    
    path('assign-new-admin/', system_admin_required(views.assign_new_admin), name='assign_new_admin'),
]

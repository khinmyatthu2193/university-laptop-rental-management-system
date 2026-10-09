from django.urls import path
from django.views.decorators.http import require_POST

from . import views
from .access import permission_required, staff_access, system_admin_required

app_name = 'rental_system'

urlpatterns = [
    # Home / Dashboard
    path('', permission_required('dashboard.view')(views.home_view), name='home'),
    path('login/', views.login_view, name='login'),
    path('signin/', views.signin_view, name='signin'),
    path('logout/', staff_access(require_POST(views.logout_view), allow_self_service_write=True), name='logout'),
    
    #KMT's Code for Student Management
    path("students/", permission_required('students.view', 'students.manage')(views.student_list), name="student_list"),
    path("students/create/", permission_required('students.manage')(views.student_create), name="student_create"),
    path("students/<int:pk>/edit/", permission_required('students.manage')(views.student_update), name="student_update"),
    path('students/import/', permission_required('students.manage')(views.import_students_excel), name='import_students'),
    path('students/import/template/', permission_required('students.manage')(views.student_import_template), name='student_import_template'),
    #End of KMT's Code
    
    path('staffs/', permission_required('staff_records.view', 'staff_records.manage')(views.staff_list), name='staff_list'),
    path('staffs/create/', permission_required('staff_records.manage')(views.staff_create), name='staff_create'),
    path('staffs/<int:pk>/edit/', permission_required('staff_records.manage')(views.staff_update), name='staff_update'),
    path("staff/import/", permission_required('staff_records.manage')(views.import_staff_excel), name="import_staff"),
    path("staff/import/template/", permission_required('staff_records.manage')(views.staff_import_template), name="staff_import_template"),
    
    #SAL's Code for Laptop Management
    path("inventory/", permission_required('inventory.view', 'inventory.manage')(views.inventory_list), name="inventory_list"),
    path("inventory/create/", permission_required('inventory.manage')(views.laptop_create), name="laptop_create"),
    path("inventory/<int:pk>/edit/", permission_required('inventory.manage')(views.laptop_update), name="laptop_update"),
    path('assignments/', permission_required('assignments.view', 'assignments.manage')(views.assigned_laptop_list), name='assigned_laptop_list'),
    path('assignments/legacy-import/', permission_required('assignments.manage')(require_POST(views.import_legacy_assignments_excel)), name='import_legacy_assignments'),
    path('assignments/legacy-template/', permission_required('assignments.manage')(views.legacy_assignments_template), name='legacy_assignments_template'),
    path('returns/', permission_required('returns.view', 'returns.manage')(views.return_laptop_list), name='return_laptop_list'),
    path('issues/', permission_required('issues.view', 'issues.manage')(views.issue_list), name='issue_list'),
    #End of SAL's Code
    path("inventory/import/", permission_required('inventory.manage')(views.import_laptops_excel), name="import_laptops"),
    path("inventory/import/template/", permission_required('inventory.manage')(views.laptop_import_template), name="laptop_import_template"),

# Quick Assign
    path('quick-assign/', permission_required('assignments.manage')(views.quick_assign), name='quick_assign'),
    
    # Admin Settings
    path('profile-settings/', staff_access(views.profile_settings), name='profile_settings'),
    path('account-settings/', staff_access(views.account_settings), name='account_settings'),
    path('system-preferences/', permission_required('system_preferences.view')(views.system_preferences), name='system_preferences'),
    path('audit-logs/', permission_required('audit_logs.view')(views.audit_logs), name='audit_logs'),
    path('update-profile/', staff_access(views.update_profile, allow_self_service_write=True), name='update_profile'),
    path('change-password/', staff_access(views.change_password, allow_self_service_write=True), name='change_password'),
    path('deactivate-account/', staff_access(require_POST(views.deactivate_account), allow_self_service_write=True), name='deactivate_account'),
    path('save-preferences/', permission_required('system_preferences.manage')(views.save_preferences), name='save_preferences'),
    
    path('assign-new-admin/', system_admin_required(views.assign_new_admin), name='assign_new_admin'),
    path('staff-access/<int:pk>/edit/', system_admin_required(views.edit_staff_access), name='edit_staff_access'),
]

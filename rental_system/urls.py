from django.urls import path
from . import views

app_name = 'rental_system'

urlpatterns = [
    # Home / Dashboard
    path('', views.home_view, name='home'),
    path('login/', views.login_view, name='login'),
    path('signin/', views.signin_view, name='signin'),
    path('logout/', views.logout_view, name='logout'),
    
    #KMT's Code for Student Management
    path("students/", views.student_list, name="student_list"), 
    path("students/create/", views.student_create, name="student_create"),
    path("students/<int:pk>/edit/", views.student_update, name="student_update"),
    path('students/import/', views.import_students_excel, name='import_students'),
    #End of KMT's Code
    
    path('staffs/', views.staff_list, name='staff_list'),
    path('staffs/create/', views.staff_create, name='staff_create'),
    path('staffs/<int:pk>/edit/', views.staff_update, name='staff_update'),
    path("staff/import/", views.import_staff_excel, name="import_staff"),
    
    #SAL's Code for Laptop Management
    path("inventory/", views.inventory_list, name="inventory_list"),
    path("inventory/create/", views.laptop_create, name="laptop_create"),
    path("inventory/<int:pk>/edit/", views.laptop_update, name="laptop_update"),
    path('assignments/', views.assigned_laptop_list, name='assigned_laptop_list'),
    path('returns/', views.return_laptop_list, name='return_laptop_list'),
    path('issues/', views.issue_list, name='issue_list'),
    #End of SAL's Code
    path("inventory/import/", views.import_laptops_excel, name="import_laptops"),

# Quick Assign
    path('quick-assign/', views.quick_assign, name='quick_assign'),
    
    # Admin Settings
    path('profile-settings/', views.profile_settings, name='profile_settings'),
    path('account-settings/', views.account_settings, name='account_settings'),
    path('system-preferences/', views.system_preferences, name='system_preferences'),
    path('audit-logs/', views.audit_logs, name='audit_logs'),
    path('update-profile/', views.update_profile, name='update_profile'),
    path('change-password/', views.change_password, name='change_password'),
    path('deactivate-account/', views.deactivate_account, name='deactivate_account'),
    path('save-preferences/', views.save_preferences, name='save_preferences'),
    
    path('assign-new-admin/', views.assign_new_admin, name='assign_new_admin'),
]
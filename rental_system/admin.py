from django.contrib import admin
from .models import (
    ManagementStaff, Person, Student, Staff, Laptop, 
    LaptopAssignment, DamageReport, RepairLog, 
    LaptopReplacement, Blacklist, AuditLog
)

# -----------------------------
# User & Role Management
# -----------------------------

@admin.register(ManagementStaff)
class ManagementStaffAdmin(admin.ModelAdmin):
    list_display = ('username', 'name', 'position', 'department', 'status', 'created_at')
    list_filter = ('status', 'department', 'position')
    search_fields = ('username', 'name', 'outlook_mail')

@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ('name', 'person_type', 'phone_number', 'outlook_mail', 'status')
    list_filter = ('person_type', 'status')
    search_fields = ('name', 'outlook_mail', 'phone_number')

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('student_id', 'full_name', 'major', 'batch_year', 'laptop')
    list_filter = ('major', 'batch_year')
    search_fields = ('student_id', 'full_name', 'email')
    # Use raw_id_fields if you have thousands of laptops to avoid slow dropdowns
    raw_id_fields = ('laptop',)

@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ('get_name', 'staff_type', 'position', 'department', 'office_section', 'laptop')
    list_filter = ('staff_type', 'staff_status', 'department')
    search_fields = ('person__name', 'phone_no')
    raw_id_fields = ('person', 'laptop')

    def get_name(self, obj):
        return obj.person.name
    get_name.short_description = 'Staff Name'

# -----------------------------
# Laptop & Asset Management
# -----------------------------

@admin.register(Laptop)
class LaptopAdmin(admin.ModelAdmin):
    list_display = ('SerialNumber', 'brand', 'name', 'processor_gen', 'for_whom', 'status')
    list_filter = ('status', 'brand', 'for_whom')
    search_fields = ('SerialNumber', 'name', 'brand')
    list_editable = ('status',) # Allows changing status directly from the list view

# -----------------------------
# Assignments & Logs
# -----------------------------

@admin.register(LaptopAssignment)
class LaptopAssignmentAdmin(admin.ModelAdmin):
    list_display = ('person', 'laptop', 'issue_date', 'expected_return_date', 'assignment_status')
    list_filter = ('assignment_status', 'academic_year')
    search_fields = ('person__name', 'laptop__SerialNumber')
    date_hierarchy = 'issue_date'

@admin.register(DamageReport)
class DamageReportAdmin(admin.ModelAdmin):
    list_display = ('laptop', 'report_date', 'replacement_status')
    list_filter = ('replacement_status',)
    search_fields = ('laptop__SerialNumber', 'damage_description')

@admin.register(RepairLog)
class RepairLogAdmin(admin.ModelAdmin):
    list_display = ('laptop', 'repair_date', 'repair_shop', 'repair_cost', 'repair_status')
    list_filter = ('repair_status', 'repair_date')
    search_fields = ('laptop__SerialNumber', 'repair_shop')

@admin.register(LaptopReplacement)
class LaptopReplacementAdmin(admin.ModelAdmin):
    list_display = ('assignment', 'old_laptop', 'new_laptop', 'replacement_date')
    search_fields = ('old_laptop__SerialNumber', 'new_laptop__SerialNumber')

# -----------------------------
# Security & Auditing
# -----------------------------

@admin.register(Blacklist)
class BlacklistAdmin(admin.ModelAdmin):
    list_display = ('person', 'blacklist_date')
    search_fields = ('person__name', 'reason')

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('staff', 'action_time', 'action_type', 'target_table', 'record_id')
    list_filter = ('action_type', 'target_table', 'action_time')
    search_fields = ('description', 'record_id')
    # Make Audit Logs read-only to preserve integrity
    readonly_fields = ('staff', 'action_time', 'action_type', 'target_table', 'record_id', 'old_value', 'new_value', 'description')

    def has_add_permission(self, request): return False
    def has_delete_permission(self, request, obj=None): return False
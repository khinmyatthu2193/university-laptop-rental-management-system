from django.contrib import admin
from django.core.exceptions import ValidationError
from .models import (
    ManagementStaff, Person, Student, Staff, Laptop, 
    LaptopAssignment, DamageReport, RepairLog, 
    LaptopReplacement, Blacklist, AuditLog, SystemPreference
)
from .services.inventory import audit_category_change, set_status

# -----------------------------
# User & Role Management
# -----------------------------

@admin.register(ManagementStaff)
class ManagementStaffAdmin(admin.ModelAdmin):
    list_display = ('username', 'name', 'role', 'position', 'department', 'status', 'created_at')
    list_filter = ('role', 'status', 'department', 'position')
    search_fields = ('username', 'name', 'outlook_mail')

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        auth_user = obj.auth_user
        auth_user.username = obj.username
        auth_user.email = obj.outlook_mail
        auth_user.first_name = obj.name
        auth_user.is_active = obj.status == 'Active'
        auth_user.save(update_fields=['username', 'email', 'first_name', 'is_active'])

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
    list_display = ('SerialNumber', 'brand', 'name', 'source', 'for_whom', 'status')
    list_filter = ('source', 'status', 'brand', 'for_whom')
    search_fields = ('SerialNumber', 'name', 'brand')

    def save_model(self, request, obj, form, change):
        previous = Laptop.objects.get(pk=obj.pk) if change else None
        if obj.source == 'Student Replacement' and (
            not obj.replacement_student_id or not obj.replacement_details
        ):
            raise ValidationError('Student Replacement requires student ID and replacement information.')
        if change and 'status' in form.changed_data:
            requested_status = obj.status
            obj.status = previous.status
            administrator = getattr(request, 'management_staff', None)
            if administrator is None:
                administrator = ManagementStaff.objects.filter(auth_user=request.user).first()
            set_status(
                obj,
                requested_status,
                administrator,
                'Administrator inventory status correction',
            )
        if change and previous and 'source' in form.changed_data:
            administrator = getattr(request, 'management_staff', None)
            if administrator is None:
                administrator = ManagementStaff.objects.filter(auth_user=request.user).first()
            audit_category_change(
                administrator, obj,
                previous.source, obj.source,
            )
        super().save_model(request, obj, form, change)

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


@admin.register(SystemPreference)
class SystemPreferenceAdmin(admin.ModelAdmin):
    list_display = ('id', 'updated_by', 'updated_at')
    readonly_fields = ('values', 'updated_by', 'updated_at')

    def has_add_permission(self, request): return False
    def has_delete_permission(self, request, obj=None): return False

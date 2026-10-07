from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

# -----------------------------
# Management Staff
# -----------------------------
class ManagementStaff(models.Model):

    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Resigned', 'Resigned'),
    ]

    ROLE_CHOICES = [
        ('SystemAdmin', 'System administrator'),
        ('Admin', 'Administrator'),
        ('ReadOnly', 'Read-only reporter'),
    ]

    auth_user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='management_profile',
    )
    name = models.CharField(max_length=30)
    username = models.CharField(max_length=50, unique=True)
    outlook_mail = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True) 
    position = models.CharField(max_length=20)
    department = models.CharField(max_length=30)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='Admin')
    permissions = models.JSONField(default=list, blank=True)
    must_change_password = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Active')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.username

    @property
    def is_account_owner(self):
        return self.username.strip().casefold() == 'daw_moe_thida'

    def has_permission(self, permission):
        """Return whether this staff account can use a UniKit capability."""
        if self.is_account_owner:
            return True
        # Keep the first-installation administrator usable until the named
        # owner account has been created.
        if self.role == 'SystemAdmin' and not type(self).objects.filter(
            username__iexact='daw_moe_thida'
        ).exists():
            return True
        return permission in (self.permissions or [])

    class Meta:
        db_table = 'management_staff'


# -----------------------------
# Person
# -----------------------------
class Person(models.Model):

    PERSON_TYPE = [
        ('Student', 'Student'),
        ('Staff', 'Staff'),
    ]

    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Inactive', 'Inactive'),
        ('Blacklisted', 'Blacklisted'),
    ]

    name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=15)
    outlook_mail = models.EmailField()
    person_type = models.CharField(max_length=20, choices=PERSON_TYPE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Active')

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'person'


# -----------------------------
# Student
# -----------------------------
class Student(models.Model):
    MAJOR_CHOICES = [
        ("CSE", "CSE"),
        ("ECE", "ECE"),
    ]

    student_id = models.CharField(max_length=50, unique=True)
    full_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    major = models.CharField(max_length=10)
    batch_year = models.IntegerField()

    laptop = models.ForeignKey('Laptop', on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.student_id
    
    class Meta:
        db_table = 'student'


# -----------------------------
# Staff (Updated with Specific Choices)
# -----------------------------
class Staff(models.Model):
    
    STAFF_TYPE_CHOICES = [
        ('Teaching', 'Teaching Staff'),
        ('Office', 'Office Staff'),
    ]

    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Relocated', 'Relocated'),
        ('Resigned', 'Resigned'),
    ]

    # Updated Department Choices for Teaching Staff
    DEPARTMENT_CHOICES = [
        ('FCST', 'FCST'),
        ('FCS', 'FCS'),
        ('FIS', 'FIS'),
        ('ITSM', 'ITSM'),
        ('FC', 'FC'),
        ('NS', 'NS'),
        ('Eng', 'Eng'),
        ('Myanmar', 'Myanmar'),
    ]

    # Updated Section Choices for Office Staff
    OFFICE_SECTION_CHOICES = [
        ('Management', 'Management'),
        ('Student Affair', 'Student Affair'),
        ('Library', 'Library'),
        ('Financial and Accounting', 'Financial and Accounting'),
    ]

    # Link to the Person table
    person = models.OneToOneField(Person, on_delete=models.CASCADE)

    # Distinguishes between Teaching and Office
    staff_type = models.CharField(max_length=20, choices=STAFF_TYPE_CHOICES)

    # Common fields
    position = models.CharField(max_length=50, help_text="Rank for Teaching, Role for Office")
    phone_no = models.CharField(max_length=20, blank=True, null=True)
    laptop = models.ForeignKey('Laptop', on_delete=models.SET_NULL, null=True, blank=True)
    staff_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Active')
    department = models.CharField(
        max_length=100, 
        choices=DEPARTMENT_CHOICES, 
        blank=True, 
        null=True, 
        help_text="Department for Teaching Staff"
    )
    
    office_section = models.CharField(
        max_length=100, 
        choices=OFFICE_SECTION_CHOICES, 
        blank=True, 
        null=True, 
        help_text="Section for Office Staff"
    )

    def __str__(self):
        return f"{self.person.name} ({self.get_staff_type_display()})"

    class Meta:
        db_table = 'staff'


# -----------------------------
# Laptop
# -----------------------------
class Laptop(models.Model):
    SerialNumber = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=100)
    brand = models.CharField(max_length=50)
    processor_gen = models.CharField(max_length=50)
    ram = models.IntegerField()
    
    storage = models.CharField(max_length=100)

    FOR_WHOM_CHOICES = [
        ('Student', 'Student'),
        ('Staff', 'Staff'),
    ]
    for_whom = models.CharField(max_length=20, choices=FOR_WHOM_CHOICES)

    STATUS_CHOICES = [
        ('Available', 'Available'),
        ('Assigned', 'Assigned'),
        ('In Repair', 'In Repair'),
        ('Damage', 'Damage'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Available')
    remark = models.CharField(max_length=255, blank=True, default='')

    def __str__(self):
        return f"{self.SerialNumber} - {self.brand} {self.name}"
    
    @property
    def model(self):
        return self.name
    
    class Meta:
        db_table = 'laptop'


# -----------------------------
# Laptop Assignment
# -----------------------------
class LaptopAssignment(models.Model):

    STATUS_CHOICES = [
        ('Issued', 'Issued'),
        ('Returned', 'Returned'),
        ('Overdue', 'Overdue'),
    ]

    person = models.ForeignKey(Person, on_delete=models.PROTECT)
    laptop = models.ForeignKey(Laptop, on_delete=models.PROTECT)

    issue_date = models.DateField()
    expected_return_date = models.DateField()
    actual_return_date = models.DateField(null=True, blank=True)

    academic_year = models.CharField(max_length=20)
    assignment_status = models.CharField(max_length=20, choices=STATUS_CHOICES)

    class Meta:
        db_table = 'laptop_assignment'
        constraints = [
            models.UniqueConstraint(
                fields=['laptop'],
                condition=Q(
                    assignment_status__in=['Issued', 'Overdue'],
                    actual_return_date__isnull=True,
                ),
                name='one_active_assignment_per_laptop',
            ),
            models.UniqueConstraint(
                fields=['person'],
                condition=Q(
                    assignment_status__in=['Issued', 'Overdue'],
                    actual_return_date__isnull=True,
                ),
                name='one_active_assignment_per_person',
            ),
            models.CheckConstraint(
                condition=Q(expected_return_date__gte=models.F('issue_date')),
                name='assignment_due_on_or_after_issue',
            ),
            models.CheckConstraint(
                condition=Q(actual_return_date__isnull=True) | Q(actual_return_date__gte=models.F('issue_date')),
                name='assignment_return_on_or_after_issue',
            ),
        ]


# -----------------------------
# Damage Report
# -----------------------------
class DamageReport(models.Model):

    REPLACEMENT_STATUS = [
        ('Yes', 'Yes'),
        ('No', 'No'),
    ]

    laptop = models.ForeignKey(Laptop, on_delete=models.PROTECT)
    assignment = models.ForeignKey(LaptopAssignment, on_delete=models.PROTECT)

    damage_description = models.TextField()
    report_date = models.DateField()
    replacement_status = models.CharField(max_length=10, choices=REPLACEMENT_STATUS)

    class Meta:
        db_table = 'damage_report'


# -----------------------------
# Repair Log
# -----------------------------
class RepairLog(models.Model):

    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Repairing', 'Repairing'),
        ('Completed', 'Completed'),
    ]

    laptop = models.ForeignKey(Laptop, on_delete=models.PROTECT)

    repair_date = models.DateField()
    issue_description = models.TextField()
    repair_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    repair_shop = models.CharField(max_length=50)
    shop_address = models.CharField(max_length=100)

    repair_status = models.CharField(max_length=20, choices=STATUS_CHOICES)

    class Meta:
        db_table = 'repair_log'


# -----------------------------
# Laptop Replacement
# -----------------------------
class LaptopReplacement(models.Model):

    assignment = models.ForeignKey(LaptopAssignment, on_delete=models.PROTECT)

    old_laptop = models.ForeignKey(
        Laptop,
        on_delete=models.PROTECT,
        related_name='old_laptop'
    )

    new_laptop = models.ForeignKey(
        Laptop,
        on_delete=models.PROTECT,
        related_name='new_laptop'
    )

    replacement_date = models.DateField()

    class Meta:
        db_table = 'laptop_replacement'


# -----------------------------
# Blacklist
# -----------------------------
class Blacklist(models.Model):

    person = models.ForeignKey(Person, on_delete=models.PROTECT)
    reason = models.TextField()
    blacklist_date = models.DateField()

    class Meta:
        db_table = 'blacklist'


# -----------------------------
# Audit Log
# -----------------------------
class AuditLog(models.Model):

    ACTION_TYPES = [
        ('Create', 'Create'),
        ('Insert', 'Insert'),
        ('Update', 'Update'),
        ('Delete', 'Delete'),
    ]

    staff = models.ForeignKey(ManagementStaff, on_delete=models.PROTECT)

    action_time = models.DateTimeField(auto_now_add=True)
    action_type = models.CharField(max_length=20, choices=ACTION_TYPES)

    target_table = models.CharField(max_length=30)
    record_id = models.CharField(max_length=30)

    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)

    description = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = 'audit_log'

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError('Audit log records are append-only.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Audit log records cannot be deleted.')


class SystemPreference(models.Model):
    """Persisted singleton-style settings for this local UniKit installation."""

    values = models.JSONField(default=dict)
    updated_by = models.ForeignKey(ManagementStaff, on_delete=models.PROTECT)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'system_preference'

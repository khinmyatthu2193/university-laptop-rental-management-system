from django.db import models

# -----------------------------
# Management Staff
# -----------------------------
class ManagementStaff(models.Model):

    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Resigned', 'Resigned'),
    ]

    name = models.CharField(max_length=30)
    username = models.CharField(max_length=50, unique=True)
    outlook_mail = models.EmailField()
    phone_number = models.CharField(max_length=20, blank=True, null=True) 
    password = models.CharField(max_length=255)
    position = models.CharField(max_length=20)
    department = models.CharField(max_length=30)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Active')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.username

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

    person = models.ForeignKey(Person, on_delete=models.CASCADE)
    laptop = models.ForeignKey(Laptop, on_delete=models.CASCADE)

    issue_date = models.DateField()
    expected_return_date = models.DateField()
    actual_return_date = models.DateField(null=True, blank=True)

    academic_year = models.CharField(max_length=20)
    assignment_status = models.CharField(max_length=20, choices=STATUS_CHOICES)

    class Meta:
        db_table = 'laptop_assignment'


# -----------------------------
# Damage Report
# -----------------------------
class DamageReport(models.Model):

    REPLACEMENT_STATUS = [
        ('Yes', 'Yes'),
        ('No', 'No'),
    ]

    laptop = models.ForeignKey(Laptop, on_delete=models.CASCADE)
    assignment = models.ForeignKey(LaptopAssignment, on_delete=models.CASCADE)

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

    laptop = models.ForeignKey(Laptop, on_delete=models.CASCADE)

    repair_date = models.DateField()
    issue_description = models.TextField()
    repair_cost = models.FloatField()

    repair_shop = models.CharField(max_length=50)
    shop_address = models.CharField(max_length=100)

    repair_status = models.CharField(max_length=20, choices=STATUS_CHOICES)

    class Meta:
        db_table = 'repair_log'


# -----------------------------
# Laptop Replacement
# -----------------------------
class LaptopReplacement(models.Model):

    assignment = models.ForeignKey(LaptopAssignment, on_delete=models.CASCADE)

    old_laptop = models.ForeignKey(
        Laptop,
        on_delete=models.CASCADE,
        related_name='old_laptop'
    )

    new_laptop = models.ForeignKey(
        Laptop,
        on_delete=models.CASCADE,
        related_name='new_laptop'
    )

    replacement_date = models.DateField()

    class Meta:
        db_table = 'laptop_replacement'


# -----------------------------
# Blacklist
# -----------------------------
class Blacklist(models.Model):

    person = models.ForeignKey(Person, on_delete=models.CASCADE)
    reason = models.TextField()
    blacklist_date = models.DateField()

    class Meta:
        db_table = 'blacklist'


# -----------------------------
# Audit Log
# -----------------------------
class AuditLog(models.Model):

    ACTION_TYPES = [
        ('Insert', 'Insert'),
        ('Update', 'Update'),
        ('Delete', 'Delete'),
    ]

    staff = models.ForeignKey(ManagementStaff, on_delete=models.CASCADE)

    action_time = models.DateTimeField(auto_now_add=True)
    action_type = models.CharField(max_length=20, choices=ACTION_TYPES)

    target_table = models.CharField(max_length=30)
    record_id = models.CharField(max_length=30)

    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)

    description = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = 'audit_log'
        

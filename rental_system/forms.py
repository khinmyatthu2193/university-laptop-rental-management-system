# forms.py
from django import forms
from .models import Student, Laptop, Staff

# Student Management
class StudentForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = ["student_id", "full_name", "email", "phone", "major", "batch_year"]
        widgets = {
            "student_id": forms.TextInput(attrs={"class": "form-control", "placeholder": "2025-MIIT-CSE-001"}),
            "full_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Student Full Name"}),
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "2025-miit-cse-001@miit.edu.mm"}),
            "phone": forms.TextInput(attrs={"class": "form-control", "placeholder": "09-xxxxxxxxx"}),
            "major": forms.Select(
                choices=[("CSE", "CSE"), ("ECE", "ECE")],
                attrs={"class": "form-select"}
            ),
            "batch_year": forms.NumberInput(attrs={"class": "form-control", "placeholder": "2025"}),
        }

# Staff Management
class StaffForm(forms.ModelForm):
    # Added person fields explicitly to handle the linked Person model in the same form if needed
    name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Full Name"}))
    outlook_mail = forms.EmailField(widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "example@miit.edu.mm"}))
    phone_number = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "09-xxxxxxxxx"}))

    class Meta:
        model = Staff
        fields = ["staff_type", "position", "department", "office_section", "staff_status"]
        widgets = {
            "staff_type": forms.Select(attrs={"class": "form-select", "id": "staffTypeSelect"}),
            "position": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Lecturer / Admin Officer"}),
            "department": forms.Select(attrs={"class": "form-select", "id": "deptSelect"}),
            "office_section": forms.Select(attrs={"class": "form-select", "id": "sectionSelect"}),
            "staff_status": forms.Select(attrs={"class": "form-select"}),
        }

# Laptop Management
class LaptopForm(forms.ModelForm):
    class Meta:
        model = Laptop
        fields = [
            "SerialNumber", "brand", "name", "processor_gen", "ram",
            "storage", "for_whom", "status", "remark"
        ]
        widgets = {
            "SerialNumber": forms.TextInput(attrs={"class": "form-control", "placeholder": "LP001"}),
            "brand": forms.TextInput(attrs={"class": "form-control", "placeholder": "HP"}),
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "EliteBook 840 G7"}),
            "processor_gen": forms.TextInput(attrs={"class": "form-control", "placeholder": "i5 11th Gen"}),
            "ram": forms.NumberInput(attrs={"class": "form-control", "placeholder": "8"}),
            "storage": forms.TextInput(attrs={"class": "form-control", "placeholder": "512GB SSD"}),
            "for_whom": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "remark": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }
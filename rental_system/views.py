from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import logout
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.hashers import make_password, check_password
from .models import Student, Laptop, ManagementStaff, Person, LaptopAssignment, AuditLog, Staff, RepairLog
from .forms import StudentForm, LaptopForm
from django.urls import reverse
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone
from django.db import transaction
import pandas as pd
import re
from datetime import datetime

ACTIVE_ASSIGNMENT_STATUSES = ('Issued', 'Overdue')


def refresh_overdue_assignments(reference_date=None):
    today = reference_date or timezone.now().date()
    active_qs = LaptopAssignment.objects.filter(actual_return_date__isnull=True)
    active_qs.filter(expected_return_date__lt=today).exclude(assignment_status='Returned').update(assignment_status='Overdue')
    active_qs.filter(expected_return_date__gte=today, assignment_status='Overdue').update(assignment_status='Issued')


def _add_one_year_safe(date_value):
    try:
        return date_value.replace(year=date_value.year + 1)
    except ValueError:
        # Handle leap day safely.
        return date_value.replace(month=2, day=28, year=date_value.year + 1)


def get_active_assignment_for_laptop(laptop):
    return LaptopAssignment.objects.select_related('person').filter(
        laptop=laptop,
        assignment_status__in=ACTIVE_ASSIGNMENT_STATUSES,
        actual_return_date__isnull=True,
    ).order_by('-id').first()


def validate_laptop_is_assignable(laptop):
    if laptop.status == 'Assigned':
        return False, f'Laptop {laptop.SerialNumber} is already assigned.'

    active_assignment = get_active_assignment_for_laptop(laptop)
    if active_assignment:
        holder = active_assignment.person.name if active_assignment.person else 'someone'
        return False, f'Laptop {laptop.SerialNumber} is already assigned to {holder}.'

    if Student.objects.filter(laptop=laptop).exists():
        return False, f'Laptop {laptop.SerialNumber} is already linked to a student.'

    if Staff.objects.filter(laptop=laptop).exists():
        return False, f'Laptop {laptop.SerialNumber} is already linked to a staff member.'

    return True, ''


def sync_laptop_assignment_statuses():
    """
    Keep laptop.status aligned with assignment ownership links.
    At minimum, any actively assigned laptop must not remain 'Available'.
    """
    active_assignment_ids = set(
        LaptopAssignment.objects.filter(
            assignment_status__in=ACTIVE_ASSIGNMENT_STATUSES,
            actual_return_date__isnull=True,
            laptop__isnull=False,
        ).values_list('laptop_id', flat=True)
    )
    linked_student_ids = set(
        Student.objects.filter(laptop__isnull=False).values_list('laptop_id', flat=True)
    )
    linked_staff_ids = set(
        Staff.objects.filter(laptop__isnull=False).values_list('laptop_id', flat=True)
    )

    assigned_ids = active_assignment_ids | linked_student_ids | linked_staff_ids
    if not assigned_ids:
        return

    Laptop.objects.filter(id__in=assigned_ids, status='Available').update(status='Assigned')


def get_or_create_student_person(student):
    person = Person.objects.filter(
        person_type='Student',
        outlook_mail=student.email,
    ).first()
    if person:
        updated = False
        if person.name != student.full_name:
            person.name = student.full_name
            updated = True
        phone = (student.phone or '')[:15]
        if phone and person.phone_number != phone:
            person.phone_number = phone
            updated = True
        if updated:
            person.save()
        return person

    return Person.objects.create(
        name=student.full_name,
        phone_number=(student.phone or '-')[:15] or '-',
        outlook_mail=student.email,
        person_type='Student',
        status='Active',
    )


def get_or_create_student_assignment(student, laptop=None):
    laptop = laptop or student.laptop
    if not laptop:
        return None

    person = get_or_create_student_person(student)
    assignment = LaptopAssignment.objects.filter(
        person=person,
        laptop=laptop,
        assignment_status__in=ACTIVE_ASSIGNMENT_STATUSES,
        actual_return_date__isnull=True,
    ).order_by('-id').first()

    if assignment:
        return assignment

    today = timezone.now().date()
    return LaptopAssignment.objects.create(
        person=person,
        laptop=laptop,
        issue_date=today,
        expected_return_date=today,
        academic_year=str(today.year),
        assignment_status='Issued',
    )


def apply_return_updates(laptop, assignment, condition, notes, cleaned_data, return_type='complete', replace=False):
    today = timezone.now().date()

    laptop.brand = cleaned_data.get('brand', laptop.brand)
    laptop.name = cleaned_data.get('name', laptop.name)
    laptop.processor_gen = cleaned_data.get('processor_gen', laptop.processor_gen)
    laptop.storage = cleaned_data.get('storage', laptop.storage)
    laptop.remark = cleaned_data.get('remark', laptop.remark)

    try:
        laptop.ram = int(cleaned_data.get('ram', laptop.ram) or laptop.ram)
    except (TypeError, ValueError):
        pass

    return_type_label = 'Annual Return' if return_type == 'annual' else 'Complete Return'
    note_parts = [f'Returned on {today}', f'Type: {return_type_label}', f'Condition: {condition}', f'Replace: {"Yes" if replace else "No"}']
    if notes:
        note_parts.append(f'Notes: {notes}')
    return_note = ' | '.join(note_parts)
    laptop.remark = return_note if not laptop.remark else f"{laptop.remark} || {return_note}"

    if return_type == 'annual':
        # Annual return checks laptop but keeps the assignment active.
        base_date = assignment.expected_return_date or today
        if base_date < today:
            base_date = today
        assignment.expected_return_date = _add_one_year_safe(base_date)
        laptop.status = 'Assigned'
        assignment.assignment_status = 'Issued'
        assignment.actual_return_date = None
    else:
        # Complete return releases the laptop back to inventory.
        laptop.status = 'Available'
        assignment.assignment_status = 'Returned'
        assignment.actual_return_date = today

    laptop.save()
    assignment.save()

    return laptop


def home_view(request):
    """
    Renders the Dashboard page using dashboard_file.html which extends home.html
    """
    # 1. Manually check if staff is logged in via session
    staff_id = request.session.get('staff_id')
    
    if not staff_id:
        return redirect('rental_system:login')

    try:
        # 2. Get the actual staff object from DB
        current_staff = ManagementStaff.objects.get(id=staff_id)
    except ManagementStaff.DoesNotExist:
        # If ID exists in session but not DB (user deleted?), logout
        return redirect('rental_system:login')

    refresh_overdue_assignments()
    sync_laptop_assignment_statuses()

    # Add the context data that dashboard_file.html expects
    from django.utils import timezone



    from .models import Laptop, LaptopAssignment, Student, Person
    from django.db.models import Count, Q
    from datetime import timedelta
    
    # Calculate dashboard statistics
    total_laptops = Laptop.objects.count()
    available_laptops = Laptop.objects.filter(status="Available").count()
    repair_laptops = Laptop.objects.filter(
        Q(status='In Repair') |
        Q(id__in=RepairLog.objects.filter(repair_status__in=['Pending', 'Repairing']).values_list('laptop_id', flat=True))
    ).distinct().count()
    damage_laptops = Laptop.objects.filter(status='Damage').count()
    assigned_laptops = Laptop.objects.filter(status='Assigned').count()
    
    total_students = Student.objects.count()
    
    # Get assignment stats
    active_assignments = LaptopAssignment.objects.filter(
        assignment_status__in=ACTIVE_ASSIGNMENT_STATUSES,
        actual_return_date__isnull=True,
    ).count()
    
    overdue_assignments = LaptopAssignment.objects.filter(
        assignment_status='Overdue'
    ).count()
    
    # Get recent assignments
    recent_assignments = LaptopAssignment.objects.select_related(
        'person', 'laptop'
    ).order_by('-issue_date')[:10]
    
    # Get persons for quick assign modal
    persons = Person.objects.filter(status='Active')[:50]
    
    # Get available laptops list for quick assign
    available_laptops_list = Laptop.objects.filter(status='Available')[:50]
    
    # Monthly data for charts (last 6 months)
    monthly_labels = []
    monthly_counts = []
    
    today = timezone.now().date()
    for i in range(5, -1, -1):
        month = today - timedelta(days=30*i)
        month_str = month.strftime('%b %Y')
        monthly_labels.append(month_str)
        
        # Count assignments in that month
        count = LaptopAssignment.objects.filter(
            issue_date__year=month.year,
            issue_date__month=month.month
        ).count()
        monthly_counts.append(count)
    
    context = {
        'title': 'Laptop Rental Dashboard',
        'user': current_staff,
        # Stats
        'total_laptops': total_laptops,
        'available_laptops': available_laptops,
        'repair_laptops': repair_laptops,
        'damage_laptops': damage_laptops,
        'assigned_laptops': assigned_laptops,
        'total_students': total_students,
        'active_assignments': active_assignments,
        'overdue_assignments': overdue_assignments,
        # Data tables
        'recent_assignments': recent_assignments,
        'persons': persons,
        'available_laptops_list': available_laptops_list,
        # Chart data
        'monthly_labels': monthly_labels,
        'monthly_counts': monthly_counts,
    }
    
    # This renders dashboard_file.html which extends home.html
    # So you'll see the sidebar from home.html and the dashboard content in the main area
    return render(request, 'dashboard_file.html', context)

def quick_assign(request):
    """Quick assign a laptop to a person"""
    if request.method == 'POST':
        person_id = request.POST.get('person')
        laptop_id = request.POST.get('laptop')
        issue_date = request.POST.get('issue_date')
        expected_return_date = request.POST.get('expected_return_date')
        academic_year = request.POST.get('academic_year')
        
        # Get the objects
        person = get_object_or_404(Person, id=person_id)
        laptop = get_object_or_404(Laptop, id=laptop_id)
        
        is_assignable, error_message = validate_laptop_is_assignable(laptop)
        if not is_assignable:
            messages.error(request, error_message)
            return redirect('rental_system:home')

        # Create the assignment
        assignment = LaptopAssignment.objects.create(
            person=person,
            laptop=laptop,
            issue_date=issue_date,
            expected_return_date=expected_return_date,
            academic_year=academic_year,
            assignment_status='Issued'
        )
        
        # Update laptop status
        laptop.status = 'Assigned'
        laptop.save()
        
        messages.success(request, f'Laptop assigned to {person.name} successfully!')
        return redirect('rental_system:home')
    
    return redirect('rental_system:home')

def logout_view(request):
    """Logs the user out by clearing the session."""
    try:
        del request.session['staff_id']
    except KeyError:
        pass
    return redirect('rental_system:login')

def login_view(request):
    """
    Handles the LOGIN logic using Outlook Email instead of username.
    """
    if request.method == 'POST':
        email_input = request.POST.get('email', '').strip().lower()  # Get email
        password = request.POST.get('password', '').strip()
        
        print("=" * 60)
        print("LOGIN ATTEMPT")
        print(f"Email entered: {email_input}")
        print(f"Password entered: {password}")
        
        # Validation
        if not email_input or not password:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': 'Please enter both email and password.'
                })
            return render(request, 'login.html', {
                'error': 'Please enter both email and password.'
            })
        
        # Validate MIIT email format
        if not email_input.endswith('@miit.edu.mm'):
            error_msg = 'Please use a valid MIIT Outlook email (@miit.edu.mm).'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': error_msg
                })
            return render(request, 'login.html', {'error': error_msg})
        
        try:
            # Find staff by outlook_mail (email) instead of username
            staff = ManagementStaff.objects.get(outlook_mail__iexact=email_input)
            print(f"User found in DB: {staff.username}")
            print(f"User email: {staff.outlook_mail}")
            print(f"User status: {staff.status}")
            print(f"DB Password Hash starts with: {staff.password[:20]}...")
            
            # Check password
            password_match = check_password(password, staff.password)
            print(f"Password match result: {password_match}")
            
            if password_match:
                print("PASSWORD MATCH! Login Success.")
                request.session['staff_id'] = staff.id
                print(f"Session created with staff_id: {staff.id}")
                print("=" * 60)
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': True,
                        'redirect_url': reverse('rental_system:home')
                    })
                return redirect('rental_system:home')
            else:
                print("PASSWORD MISMATCH! Login Failed.")
                error_msg = 'Invalid email or password. Please try again.'
                
        except ManagementStaff.DoesNotExist:
            print(f"USER NOT FOUND with email: {email_input}")
            error_msg = 'Invalid email or password. Please try again.'
        
        print("=" * 60)
        
        # Error response
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'error': error_msg
            })
        return render(request, 'login.html', {
            'error': error_msg
        })
    
    return render(request, 'login.html')

def signin_view(request):
    """
    Handles the REGISTRATION (Sign Up) logic.
    """
    if request.method == 'POST':
        # 1. Capture data
        name = request.POST.get('name')
        outlook_mail = request.POST.get('email') 
        position = request.POST.get('position')
        department = request.POST.get('department')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        # 2. Validation: Passwords match?
        if password != confirm_password:
            return render(request, 'signin.html', {
                'error': 'Passwords do not match!'
            })

        # 3. Validation: Name taken?
        if ManagementStaff.objects.filter(username=name).exists():
            return render(request, 'signin.html', {
                'error': 'This name is already taken. Please use a different name.'
            })

        # 4. Create the new staff member
        new_staff = ManagementStaff.objects.create(
            username=name,
            name=name,
            outlook_mail=outlook_mail, 
            position=position,
            department=department,
            password=make_password(password)
        )

        # 5. Automatically log them in (Create session)
        request.session['staff_id'] = new_staff.id
        return redirect('rental_system:home')

    return render(request, 'signin.html')


##### KMT's Code for Student Management #####
def student_list(request):
    students = Student.objects.select_related("laptop").all()

    # Filters
    major = request.GET.get("major")
    batch = request.GET.get("batch")
    search = request.GET.get("search", "").strip()
    selected_sort = request.GET.get("sort", "newest")

    if major:
        students = students.filter(major=major)

    if batch:
        students = students.filter(batch_year=batch)

    if search:
        students = students.filter(
            Q(student_id__icontains=search) |
            Q(full_name__icontains=search) |
            Q(email__icontains=search)
        )

    # Sort by
    if selected_sort == "oldest":
        students = students.order_by("id")
    elif selected_sort == "az":
        students = students.order_by("full_name")
    elif selected_sort == "za":
        students = students.order_by("-full_name")
    else:  # newest
        students = students.order_by("-id")

    available_laptops_count = Laptop.objects.filter(status='Available').count()

    return render(request, "student_list.html", {
        "students": students,
        "form": StudentForm(),
        "majors": ["CSE", "ECE"],
        "years": range(2015, 2050),
        "view": request.GET.get("view", "table"),
        "search_query": search,
        "available_laptops_count": available_laptops_count,
        "selected_sort": selected_sort,
    })

def student_create(request):
    if request.method == "POST":
        form = StudentForm(request.POST)
        if form.is_valid():  # Validation 
            form.save()
            messages.success(request, 'Student created successfully!')
            return redirect('rental_system:student_list')
        else:
         
            messages.error(request, 'Please correct the errors below.')
           
            students = Student.objects.select_related("laptop").all()
            return render(request, "student_list.html", {
                "students": students,
                "form": form,  
                "majors": ["CSE", "ECE"],
                "years": range(2015, 2050),
                "view": request.GET.get("view", "table"),
                "show_form": True,  
            })
    return redirect('rental_system:student_list')


def student_update(request, pk):
    student = get_object_or_404(Student, pk=pk)
    print("\n" + "="*50)
    print(f"STUDENT UPDATE VIEW CALLED for student ID: {pk}")
    print(f"Request method: {request.method}")
    
    if request.method == "POST":
        print("POST data received:")
        for key, value in request.POST.items():
            print(f"  {key}: {value}")
        
        form = StudentForm(request.POST, instance=student)
        
        # မပြင်ခင် အဟောင်းတန်ဖိုးတွေကိုသိမ်းထား
        old_data = {
            'student_id': student.student_id,
            'full_name': student.full_name,
            'email': student.email,
            'phone': student.phone,
            'major': student.major,
            'batch_year': student.batch_year
        }
        print(f"\nOLD VALUES (from database):")
        for key, value in old_data.items():
            print(f"  {key}: {value}")
        
        if form.is_valid():
            print("\nFORM IS VALID")
            
            # Form ထဲက တန်ဖိုးတွေကိုယူမယ်
            new_student_id = request.POST.get('student_id', '').strip()
            new_full_name = request.POST.get('full_name', '').strip()
            new_email = request.POST.get('email', '').strip()
            new_phone = request.POST.get('phone', '').strip()
            new_major = request.POST.get('major', '').strip()
            new_batch_year = request.POST.get('batch_year', '').strip()
            
            print(f"\nNEW VALUES (from form):")
            print(f"  student_id: {new_student_id}")
            print(f"  full_name: {new_full_name}")
            print(f"  email: {new_email}")
            print(f"  phone: {new_phone}")
            print(f"  major: {new_major}")
            print(f"  batch_year: {new_batch_year}")
            
            # Update လုပ်
            updated_student = form.save()
            print(f"\nSTUDENT SAVED: ID={updated_student.id}")
            
            # ပြောင်းလဲမှုတွေကိုရှာမယ်
            changes = []
            changed_fields = []
            
            # တစ်ခုချင်းစီကိုနှိုင်းယှဉ်မယ်
            if str(old_data['student_id']) != str(new_student_id):
                changes.append(f"Roll Number: '{old_data['student_id']}' → '{new_student_id}'")
                changed_fields.append('student_id')
                print(f"✓ student_id changed: {old_data['student_id']} → {new_student_id}")
            
            if old_data['full_name'] != new_full_name:
                changes.append(f"Name: '{old_data['full_name']}' → '{new_full_name}'")
                changed_fields.append('full_name')
                print(f"✓ full_name changed: {old_data['full_name']} → {new_full_name}")
            
            if old_data['email'] != new_email:
                changes.append(f"Email: '{old_data['email']}' → '{new_email}'")
                changed_fields.append('email')
                print(f"✓ email changed: {old_data['email']} → {new_email}")
            
            if str(old_data['phone']) != str(new_phone):
                old_phone = old_data['phone'] or 'N/A'
                new_phone_display = new_phone or 'N/A'
                changes.append(f"Phone: '{old_phone}' → '{new_phone_display}'")
                changed_fields.append('phone')
                print(f"✓ phone changed: {old_phone} → {new_phone_display}")
            
            if old_data['major'] != new_major:
                changes.append(f"Major: {old_data['major']} → {new_major}")
                changed_fields.append('major')
                print(f"✓ major changed: {old_data['major']} → {new_major}")
            
            if int(old_data['batch_year']) != int(new_batch_year):
                changes.append(f"Batch: {old_data['batch_year']} → {new_batch_year}")
                changed_fields.append('batch_year')
                print(f"✓ batch_year changed: {old_data['batch_year']} → {new_batch_year}")
            
            print(f"\nCHANGES FOUND: {len(changes)}")
            for i, change in enumerate(changes):
                print(f"  Change {i+1}: {change}")
            
            # Audit Log ဖန်တီးခြင်း
            staff_id = request.session.get('staff_id')
            print(f"\nStaff ID from session: {staff_id}")
            
            if staff_id:
                try:
                    staff = ManagementStaff.objects.get(id=staff_id)
                    print(f"Staff found: {staff.username}")
                    
                    # Description ကိုစီစဉ်မယ်
                    if changes:
                        description = f"[Roll Number: {updated_student.student_id}] Updated fields: "
                        description += ", ".join(changed_fields)
                        description += ". Details: " + "; ".join(changes)
                    else:
                        description = f"[Roll Number: {updated_student.student_id}] No changes made"
                    
                    print(f"\nDESCRIPTION: {description}")
                    
                    # Old value နဲ့ New value
                    old_value_str = f"ID:{old_data['student_id']}, Name:{old_data['full_name']}, Email:{old_data['email']}, Major:{old_data['major']}"
                    new_value_str = f"ID:{updated_student.student_id}, Name:{updated_student.full_name}, Email:{updated_student.email}, Major:{updated_student.major}"
                    
                    # Audit Log သိမ်းမယ်
                    audit_log = AuditLog.objects.create(
                        staff=staff,
                        action_type='Update',
                        target_table='student',
                        record_id=updated_student.id,
                        old_value=old_value_str,
                        new_value=new_value_str,
                        description=description
                    )
                    print(f"✅ AUDIT LOG CREATED: ID={audit_log.id}")
                    print(f"   Description: {audit_log.description}")
                    
                except ManagementStaff.DoesNotExist:
                    print(f"❌ Staff with ID {staff_id} not found!")
                except Exception as e:
                    print(f"❌ Error creating audit log: {str(e)}")
            else:
                print("❌ No staff_id in session!")
            
            messages.success(request, 'Student updated successfully!')
            return redirect('rental_system:student_list')
        else:
            print("\n❌ FORM IS NOT VALID")
            print(f"Form errors: {form.errors}")
            # ... existing error handling ...
    
    return redirect('rental_system:student_list')


#To import from excel file

def import_students_excel(request):
    if request.method != 'POST':
        return redirect('rental_system:student_list')

    file = request.FILES.get('file')
    if not file:
        messages.error(request, "Please choose an Excel file.")
        return redirect('rental_system:student_list')

    try:
        df = pd.read_excel(file)
    except Exception:
        messages.error(request, "Could not read the Excel file.")
        return redirect('rental_system:student_list')

    required_columns = ['student_id', 'full_name', 'email', 'phone', 'major', 'batch_year']
    missing_columns = [col for col in required_columns if col not in df.columns]

    if missing_columns:
        messages.error(
            request,
            "Missing required columns: " + ", ".join(missing_columns)
        )
        return redirect('rental_system:student_list')

    imported_count = 0

    for _, row in df.iterrows():
        student_id = str(row.get('student_id', '')).strip()
        if not student_id:
            continue

        Student.objects.update_or_create(
            student_id=student_id,
            defaults={
                'full_name': str(row.get('full_name', '')).strip(),
                'email': str(row.get('email', '')).strip(),
                'phone': str(row.get('phone', '')).strip(),
                'major': str(row.get('major', '')).strip(),
                'batch_year': int(row.get('batch_year', 0)) if str(row.get('batch_year', '')).strip() else 0,
            }
        )
        imported_count += 1

    messages.success(request, f"{imported_count} students imported successfully!")
    return redirect('rental_system:student_list')
### End of KMT's Code ###

### SAL's Code for Laptop Management ##
def inventory_list(request):
    sync_laptop_assignment_statuses()
    laptops = Laptop.objects.all()

    status = request.GET.get("status")
    search = request.GET.get("search", "").strip()
    selected_sort = request.GET.get("sort", "newest")

    if status == "Replace":
        laptops = laptops.filter(remark__icontains="Replace: Yes")
    elif status and status != "All":
        laptops = laptops.filter(status=status)

    if search:
        laptops = laptops.filter(
            Q(SerialNumber__icontains=search) |
            Q(brand__icontains=search) |
            Q(name__icontains=search)
        )

    if selected_sort == "oldest":
        laptops = laptops.order_by("id")
    elif selected_sort == "az":
        laptops = laptops.order_by("SerialNumber")
    elif selected_sort == "za":
        laptops = laptops.order_by("-SerialNumber")
    else:
        selected_sort = "az"
        laptops = laptops.order_by("SerialNumber")

    refresh_overdue_assignments()

    active_assignments = LaptopAssignment.objects.select_related('person', 'laptop').filter(
        assignment_status__in=ACTIVE_ASSIGNMENT_STATUSES,
        actual_return_date__isnull=True,
        laptop__isnull=False,
    )

    assigned_map = {}

    for a in active_assignments:
        assigned_map[a.laptop_id] = {
            'name': a.person.name,
            'type': a.person.person_type,
            'extra': a.person.outlook_mail,
        }

    # Include students and staff who are directly linked to laptops even if no active LaptopAssignment exists.
    for student in Student.objects.filter(laptop__isnull=False).select_related('laptop'):
        if student.laptop_id not in assigned_map:
            assigned_map[student.laptop_id] = {
                'name': student.full_name,
                'type': 'Student',
                'extra': student.email,
            }

    for staff in Staff.objects.filter(laptop__isnull=False).select_related('person', 'laptop'):
        if staff.laptop_id not in assigned_map:
            assigned_map[staff.laptop_id] = {
                'name': staff.person.name,
                'type': 'Staff',
                'extra': staff.person.outlook_mail,
            }

    status_list = ["All", "Available", "Assigned", "In Repair", "Damage", "Replace"]
    available_laptops_count = Laptop.objects.filter(status='Available').count()

    return render(request, "inventory_list.html", {
        "laptops": laptops,
        "form": LaptopForm(),
        "status_active": status or "All",
        "status_list": status_list,
        "assigned_map": assigned_map,
        "search_query": search,
        "available_laptops_count": available_laptops_count,
        "selected_sort": selected_sort,
    })

def laptop_create(request):
    if request.method == "POST":
        form = LaptopForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Laptop added successfully!')
        else:
            messages.error(request, 'Could not add laptop. Please check the form values.')
    return redirect('rental_system:inventory_list')


def laptop_update(request, pk):
    laptop = get_object_or_404(Laptop, pk=pk)
    if request.method == "POST":
        form = LaptopForm(request.POST, instance=laptop)
        if form.is_valid():
            form.save()
            messages.success(request, 'Laptop updated successfully!')
        else:
            messages.error(request, 'Could not update laptop. Please check the form values.')
    return redirect('rental_system:inventory_list')


#To import from excel file
def import_laptops_excel(request):
    if request.method != 'POST':
        return redirect('rental_system:inventory_list')

    file = request.FILES.get('file')
    if not file:
        messages.error(request, "Please choose an Excel file.")
        return redirect('rental_system:inventory_list')

    try:
        df = pd.read_excel(file)
    except Exception:
        messages.error(request, "Could not read the Excel file.")
        return redirect('rental_system:inventory_list')

    required_columns = [
        'SerialNumber', 'name', 'brand', 'processor_gen',
        'ram', 'storage', 'for_whom', 'status', 'remark'
    ]

    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        messages.error(
            request,
            "Missing required columns: " + ", ".join(missing_columns)
        )
        return redirect('rental_system:inventory_list')

    imported_count = 0

    for _, row in df.iterrows():
        serial_number = str(row.get('SerialNumber', '')).strip()
        if not serial_number:
            continue

        for_whom = str(row.get('for_whom', '')).strip()
        if for_whom not in ['Student', 'Staff']:
            for_whom = 'Student'

        status = str(row.get('status', '')).strip()
        if status not in ['Available', 'Assigned', 'In Repair', 'Damage']:
            status = 'Available'

        ram_value = row.get('ram', 0)
        try:
            ram_value = int(ram_value)
        except (TypeError, ValueError):
            ram_value = 0

        Laptop.objects.update_or_create(
            SerialNumber=serial_number,
            defaults={
                'name': str(row.get('name', '')).strip(),
                'brand': str(row.get('brand', '')).strip(),
                'processor_gen': str(row.get('processor_gen', '')).strip(),
                'ram': ram_value,
                'storage': str(row.get('storage', '')).strip(),
                'for_whom': for_whom,
                'status': status,
                'remark': str(row.get('remark', '')).strip(),
            }
        )
        imported_count += 1

    messages.success(request, f"{imported_count} laptops imported successfully!")
    return redirect('rental_system:inventory_list')


def assigned_laptop_list(request):
    refresh_overdue_assignments()

    students = Student.objects.select_related('laptop').order_by('full_name')
    staffs = Staff.objects.select_related('person').order_by('person__name')
    available_laptops = Laptop.objects.filter(status='Available').order_by('SerialNumber')
    available_laptops_count = available_laptops.count()
    assigned_students = students.exclude(laptop=None)
    assigned_staff_assignments = LaptopAssignment.objects.select_related('person', 'laptop').filter(
        person__person_type='Staff',
        assignment_status__in=ACTIVE_ASSIGNMENT_STATUSES,
        actual_return_date__isnull=True,
    ).order_by('person__name')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'assign':
            student_id = (request.POST.get('student_id') or '').strip()
            staff_id = (request.POST.get('staff_id') or '').strip()
            laptop_id = request.POST.get('laptop_id')

            if not laptop_id:
                messages.error(request, 'Please choose a laptop to assign.')
                return redirect('rental_system:assigned_laptop_list')
            if student_id and staff_id:
                messages.error(request, 'Please choose either a student or a staff member, not both.')
                return redirect('rental_system:assigned_laptop_list')
            if not student_id and not staff_id:
                messages.error(request, 'Please choose a student or a staff member.')
                return redirect('rental_system:assigned_laptop_list')

            laptop = get_object_or_404(Laptop, id=laptop_id)
            is_assignable, error_message = validate_laptop_is_assignable(laptop)
            if not is_assignable:
                messages.error(request, error_message)
                return redirect('rental_system:assigned_laptop_list')

            if student_id:
                student = get_object_or_404(Student, id=student_id)
                if student.laptop:
                    messages.error(request, f'{student.full_name} already has a laptop assigned.')
                elif laptop.for_whom != 'Student':
                    messages.error(request, f'Laptop {laptop.SerialNumber} is designated for {laptop.for_whom.lower()}s only.')
                else:
                    student.laptop = laptop
                    student.save()
                    get_or_create_student_assignment(student, laptop)
                    laptop.status = 'Assigned'
                    laptop.save()
                    messages.success(request, f'{laptop.SerialNumber} assigned to student {student.full_name}.')
                return redirect('rental_system:assigned_laptop_list')

            staff = get_object_or_404(Staff.objects.select_related('person'), id=staff_id)
            active_assignment = LaptopAssignment.objects.filter(
                person=staff.person,
                assignment_status__in=ACTIVE_ASSIGNMENT_STATUSES,
                actual_return_date__isnull=True,
            ).first()
            if active_assignment:
                messages.error(request, f'{staff.person.name} already has a laptop assigned.')
            elif laptop.for_whom != 'Staff':
                messages.error(request, f'Laptop {laptop.SerialNumber} is designated for {laptop.for_whom.lower()}s only.')
            else:
                LaptopAssignment.objects.create(
                    person=staff.person,
                    laptop=laptop,
                    issue_date=timezone.now().date(),
                    expected_return_date=timezone.now().date(),
                    academic_year=str(timezone.now().year),
                    assignment_status='Issued',
                )
                laptop.status = 'Assigned'
                laptop.save()
                messages.success(request, f'{laptop.SerialNumber} assigned to staff {staff.person.name}.')
            return redirect('rental_system:assigned_laptop_list')

    return render(request, 'assigned_laptop_list.html', {
        'students': students,
        'staffs': staffs,
        'available_laptops_list': available_laptops,
        'available_count': available_laptops.count(),
        'assigned_students': assigned_students,
        'assigned_staff_assignments': assigned_staff_assignments,
        'assigned_count': assigned_students.count() + assigned_staff_assignments.count(),
        'available_laptops_count': available_laptops_count,
    })


def return_laptop_list(request):
    refresh_overdue_assignments()

    assigned_students = list(Student.objects.select_related('laptop').exclude(laptop=None).order_by('full_name'))
    available_laptops_count = Laptop.objects.filter(status='Available').count()
    assigned_staff_assignments = LaptopAssignment.objects.select_related('person', 'laptop').filter(
        person__person_type='Staff',
        assignment_status__in=ACTIVE_ASSIGNMENT_STATUSES,
        actual_return_date__isnull=True,
    ).order_by('person__name')

    # Filter staff assignments
    staff_search = (request.GET.get('staff_search') or '').strip().lower()
    staff_department = (request.GET.get('staff_department') or '').strip()

    if staff_search:
        assigned_staff_assignments = assigned_staff_assignments.filter(
            Q(person__name__icontains=staff_search) | Q(laptop__SerialNumber__icontains=staff_search)
        )

    if staff_department:
        assigned_staff_assignments = assigned_staff_assignments.filter(person__staff__department=staff_department)

    student_emails = [s.email.lower() for s in assigned_students if s.email]
    student_people = Person.objects.filter(person_type='Student', outlook_mail__in=student_emails)
    student_people_by_email = {p.outlook_mail.lower(): p for p in student_people}
    student_active_assignments = LaptopAssignment.objects.filter(
        person_id__in=[p.id for p in student_people],
        assignment_status__in=ACTIVE_ASSIGNMENT_STATUSES,
        actual_return_date__isnull=True,
    ).select_related('person')
    student_assignment_by_person_id = {a.person_id: a for a in student_active_assignments}
    for student in assigned_students:
        person = student_people_by_email.get((student.email or '').lower())
        student.active_assignment = student_assignment_by_person_id.get(person.id) if person else None
    completed_returns_qs = LaptopAssignment.objects.select_related('person', 'laptop').filter(
        assignment_status='Returned',
        actual_return_date__isnull=False,
        person__person_type='Student',
    ).order_by('-actual_return_date', '-id')

    completed_returns = list(completed_returns_qs)
    for assignment in completed_returns:
        replace_status = 'No'
        remark_text = (assignment.laptop.remark or '')
        # Hide " | Replace: Yes/No" from table remark display only.
        assignment.display_remark = re.sub(r'\s*\|\s*Replace:\s*(Yes|No)', '', remark_text).strip() or '-'
        if remark_text and assignment.actual_return_date:
            # remark format added on return: "Returned on YYYY-MM-DD | Condition: ... | Replace: Yes/No"
            marker = f"Returned on {assignment.actual_return_date}"
            segments = [seg.strip() for seg in remark_text.split('||')]
            for seg in segments:
                if marker in seg and 'Replace: Yes' in seg:
                    replace_status = 'Yes'
                    break
        assignment.replace_status = replace_status

    # Filter completed returns for students
    history_search = (request.GET.get('history_search') or '').strip().lower()
    history_batch = (request.GET.get('history_batch') or '').strip()

    filtered_completed_returns = []
    for assignment in completed_returns:
        student = Student.objects.filter(email=assignment.person.outlook_mail).first()
        if student:
            student_roll = (student.student_id or '').strip().lower()
            if history_batch and str(student.batch_year) != history_batch:
                continue
            if history_search:
                if not (
                    history_search in assignment.person.name.lower() or
                    history_search in assignment.laptop.SerialNumber.lower() or
                    history_search in student_roll
                ):
                    continue
            filtered_completed_returns.append(assignment)

    # Get distinct batch years for filters
    history_batches = [str(b) for b in Student.objects.values_list('batch_year', flat=True).distinct().order_by('batch_year')]

    active_assignments = LaptopAssignment.objects.filter(
        assignment_status__in=ACTIVE_ASSIGNMENT_STATUSES,
        actual_return_date__isnull=True,
    )
    annual_due_date = active_assignments.order_by('-expected_return_date').values_list('expected_return_date', flat=True).first()

    search_query = (request.GET.get('search') or '').strip().lower()
    status_filter = (request.GET.get('status') or 'all').strip().lower()
    type_filter = (request.GET.get('type') or 'all').strip().lower()
    batch_filter = (request.GET.get('batch') or '').strip()

    assigned_records = []
    for student in assigned_students:
        assignment = getattr(student, 'active_assignment', None)
        if assignment and assignment.assignment_status in ACTIVE_ASSIGNMENT_STATUSES:
            assigned_records.append({
                'owner_type': 'student',
                'owner_id': student.id,
                'person_type': 'Student',
                'name': student.full_name,
                'laptop_label': f'{student.laptop.SerialNumber} - {student.laptop.brand} {student.laptop.name}',
                'laptop_serial': student.laptop.SerialNumber,
                'expected_return_date': assignment.expected_return_date,
                'assignment_status': assignment.assignment_status,
                'assignment_id': assignment.id,
                'batch_year': str(student.batch_year or ''),
            })

    if search_query:
        assigned_records = [
            r for r in assigned_records
            if search_query in r['name'].lower() or search_query in r['laptop_serial'].lower()
        ]

    if status_filter in ('issued', 'overdue'):
        assigned_records = [r for r in assigned_records if r['assignment_status'].lower() == status_filter]

    if type_filter in ('student', 'staff'):
        assigned_records = [r for r in assigned_records if r['owner_type'] == type_filter]

    if batch_filter:
        assigned_records = [
            r for r in assigned_records
            if r['owner_type'] == 'student' and r['batch_year'] == batch_filter
        ]

    # Put overdue at top by default for easier follow-up.
    assigned_records = sorted(
        assigned_records,
        key=lambda r: (
            0 if r['assignment_status'] == 'Overdue' else 1,
            r['expected_return_date'] or timezone.now().date(),
            r['name'].lower(),
        ),
    )

    # Keep batch filter behavior consistent with Student page.
    batch_years = [str(y) for y in range(2015, 2050)]

    if request.method == 'POST':
        action = request.POST.get('action', 'process_return')
        if action == 'set_annual_due_date':
            due_date_raw = (request.POST.get('annual_due_date') or '').strip()
            if not due_date_raw:
                messages.error(request, 'Please choose an annual return due date.')
                return redirect('rental_system:return_laptop_list')

            try:
                due_date = datetime.strptime(due_date_raw, '%Y-%m-%d').date()
            except ValueError:
                messages.error(request, 'Invalid date format for annual return due date.')
                return redirect('rental_system:return_laptop_list')

            updated_count = active_assignments.update(expected_return_date=due_date)
            refresh_overdue_assignments()
            messages.success(request, f'Annual return due date set to {due_date} for {updated_count} active assignment(s).')
            return redirect('rental_system:return_laptop_list')

        owner_type = request.POST.get('owner_type', 'student')
        owner_id = request.POST.get('owner_id')
        return_type = request.POST.get('return_type', 'complete')
        condition = request.POST.get('condition', 'Excellent')
        replace = request.POST.get('replace') == 'on'
        notes = request.POST.get('notes', '').strip()
        cleaned_data = {
            'brand': request.POST.get('brand', '').strip(),
            'name': request.POST.get('name', '').strip(),
            'processor_gen': request.POST.get('processor_gen', '').strip(),
            'ram': request.POST.get('ram', '').strip(),
            'storage': request.POST.get('storage', '').strip(),
            'remark': request.POST.get('remark', '').strip(),
        }

        if owner_type == 'staff':
            staff = get_object_or_404(Staff.objects.select_related('person'), id=owner_id)
            active_assignment = LaptopAssignment.objects.select_related('laptop', 'person').filter(
                person=staff.person,
                assignment_status__in=ACTIVE_ASSIGNMENT_STATUSES,
                actual_return_date__isnull=True,
            ).first()
            if not active_assignment or not active_assignment.laptop:
                messages.error(request, 'This staff member does not currently have a laptop assigned.')
                return redirect('rental_system:return_laptop_list')

            # Force complete return for staff
            return_type = 'complete'
            laptop = apply_return_updates(
                active_assignment.laptop,
                active_assignment,
                condition,
                notes,
                cleaned_data,
                return_type=return_type,
                replace=replace,
            )
        else:
            student = get_object_or_404(Student.objects.select_related('laptop'), id=owner_id)
            if not student.laptop:
                messages.error(request, 'This student does not currently have a laptop assigned.')
                return redirect('rental_system:return_laptop_list')

            active_assignment = get_or_create_student_assignment(student, student.laptop)
            laptop = student.laptop
            if return_type == 'complete':
                student.laptop = None
                student.save()
            laptop = apply_return_updates(
                laptop,
                active_assignment,
                condition,
                notes,
                cleaned_data,
                return_type=return_type,
                replace=replace,
            )

        if return_type == 'annual':
            messages.success(request, f'Annual return completed for {laptop.SerialNumber}. Inventory status remains {laptop.status}.')
        else:
            messages.success(request, f'Complete return completed for {laptop.SerialNumber}. Inventory status is now {laptop.status}.')
        return redirect('rental_system:return_laptop_list')

    return render(request, 'return_laptop_list.html', {
        'assigned_students': assigned_students,
        'assigned_staff_assignments': assigned_staff_assignments,
        'assigned_records': assigned_records,
        'assigned_records_count': len(assigned_records),
        'completed_returns': filtered_completed_returns,
        'completed_returns_count': len(filtered_completed_returns),
        'selected_owner_type': request.GET.get('owner_type', ''),
        'selected_owner_id': request.GET.get('owner_id', ''),
        'available_laptops_count': available_laptops_count,
        'annual_due_date': annual_due_date,
        'overdue_count': active_assignments.filter(assignment_status='Overdue').count(),
        'search_query': request.GET.get('search', ''),
        'status_filter': status_filter,
        'type_filter': type_filter,
        'batch_filter': batch_filter,
        'batch_years': batch_years,
        'history_search': history_search,
        'history_batch': history_batch,
        'history_batches': history_batches,
        'staff_search': staff_search,
        'staff_department': staff_department,
        'departments': Staff.DEPARTMENT_CHOICES,
    })


def issue_list(request):
    repair_logs = RepairLog.objects.select_related('laptop').order_by('-repair_date', '-id')
    active_issues = repair_logs.exclude(repair_status='Completed')
    available_for_issue = Laptop.objects.order_by('SerialNumber')
    available_laptops_count = Laptop.objects.filter(status='Available').count()

    if request.method == 'POST':
        action = request.POST.get('action', 'create')

        if action == 'create':
            laptop = get_object_or_404(Laptop, id=request.POST.get('laptop_id'))
            issue_type = request.POST.get('issue_type', 'General')
            description = request.POST.get('issue_description', '').strip()
            reported_by = request.POST.get('reported_by', '').strip()
            priority = request.POST.get('priority', 'Medium')

            if not description or not reported_by:
                messages.error(request, 'Please fill in the issue description and reporter name.')
                return redirect('rental_system:issue_list')

            RepairLog.objects.create(
                laptop=laptop,
                repair_date=timezone.now().date(),
                issue_description=f'Type: {issue_type} | Priority: {priority} | Reported by: {reported_by} | Details: {description}',
                repair_cost=0,
                repair_shop='Pending',
                shop_address='Pending',
                repair_status='Pending',
            )
            laptop.status = 'In Repair'
            laptop.save()
            messages.success(request, f'Issue reported for {laptop.SerialNumber}.')
            return redirect('rental_system:issue_list')

        issue = get_object_or_404(RepairLog.objects.select_related('laptop'), id=request.POST.get('issue_id'))
        if action == 'repairing':
            issue.repair_status = 'Repairing'
            issue.save()
            issue.laptop.status = 'In Repair'
            issue.laptop.save()
            messages.success(request, f'{issue.laptop.SerialNumber} is now under repair.')
        elif action == 'complete':
            issue.repair_status = 'Completed'
            issue.save()
            issue.laptop.status = 'Available'
            issue.laptop.save()
            messages.success(request, f'Issue for {issue.laptop.SerialNumber} marked as completed.')
        return redirect('rental_system:issue_list')

    return render(request, 'issue_list.html', {
        'issues': repair_logs,
        'active_issues_count': active_issues.count(),
        'repairing_count': repair_logs.filter(repair_status='Repairing').count(),
        'available_for_issue': available_for_issue,
        'available_laptops_count': available_laptops_count,
    })

# Add these new view functions to your views.py

def profile_settings(request):
    """Display profile settings page"""
    staff_id = request.session.get('staff_id')
    if not staff_id:
        return redirect('rental_system:login')
    
    try:
        current_staff = ManagementStaff.objects.get(id=staff_id)
    except ManagementStaff.DoesNotExist:
        return redirect('rental_system:login')
    
    context = {
        'user': current_staff,
        'title': 'Profile Settings',
    }
    return render(request, 'profile_settings.html', context)

def account_settings(request):
    """Display account settings page"""
    staff_id = request.session.get('staff_id')
    if not staff_id:
        return redirect('rental_system:login')
    
    try:
        current_staff = ManagementStaff.objects.get(id=staff_id)
    except ManagementStaff.DoesNotExist:
        return redirect('rental_system:login')
    
    context = {
        'user': current_staff,
        'title': 'Account Settings',
    }
    return render(request, 'account_settings.html', context)

def system_preferences(request):
    """Display system preferences page"""
    staff_id = request.session.get('staff_id')
    if not staff_id:
        return redirect('rental_system:login')
    
    try:
        current_staff = ManagementStaff.objects.get(id=staff_id)
    except ManagementStaff.DoesNotExist:
        return redirect('rental_system:login')
    
    context = {
        'user': current_staff,
        'title': 'System Preferences',
    }
    return render(request, 'system_preferences.html', context)

def audit_logs(request):
    """Display audit logs page with filters and pagination"""
    print("=" * 50)
    print("AUDIT LOGS VIEW CALLED")
    
    staff_id = request.session.get('staff_id')
    if not staff_id:
        return redirect('rental_system:login')
    
    try:
        current_staff = ManagementStaff.objects.get(id=staff_id)
    except ManagementStaff.DoesNotExist:
        return redirect('rental_system:login')
    
    from .models import AuditLog
    from django.core.paginator import Paginator
    from django.db.models import Q
    # Base queryset
    logs = AuditLog.objects.select_related('staff').all()
    
    # Apply filters
    # 1. Table filter
    table_filter = request.GET.get('table')
    if table_filter:
        logs = logs.filter(target_table=table_filter)
    
    # 2. Action filter
    action_filter = request.GET.get('action')
    if action_filter:
        logs = logs.filter(action_type=action_filter)
    
    # 3. Staff filter
    staff_filter = request.GET.get('staff')
    if staff_filter and staff_filter.isdigit():
        logs = logs.filter(staff_id=int(staff_filter))
    
    # 4. Search in description
    search_query = request.GET.get('search')
    if search_query:
        logs = logs.filter(
            Q(description__icontains=search_query) |
            Q(target_table__icontains=search_query) |
            Q(action_type__icontains=search_query) |
            Q(record_id__icontains=search_query)
        )
    
    # 5. Sorting
    sort_by = request.GET.get('sort', 'time')
    order = request.GET.get('order', 'desc')
    
    if sort_by == 'time':
        logs = logs.order_by('-action_time' if order == 'desc' else 'action_time')
    elif sort_by == 'staff':
        logs = logs.order_by('-staff__name' if order == 'desc' else 'staff__name')
    else:
        logs = logs.order_by('-action_time')  # Default
    
    # Get unique tables for filter dropdown
    tables = AuditLog.objects.values_list('target_table', flat=True).distinct().order_by('target_table')
    
    # Get all staff for filter dropdown
    staff_list = ManagementStaff.objects.filter(status='Active').order_by('name')
    
    # Pagination
    paginator = Paginator(logs, 20)  # 20 logs per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    print(f"Total logs: {logs.count()}")
    print(f"Showing page {page_number} of {paginator.num_pages}")
    
    context = {
        'user': current_staff,
        'logs': page_obj,
        'tables': tables,
        'staff_list': staff_list,
        'title': 'Audit Logs',
    }
    return render(request, 'audit_logs.html', context)

def update_profile(request):
    """Handle profile update form submission - prevents email and department changes"""
    print("=" * 50)
    print("UPDATE PROFILE VIEW CALLED")
    print(f"Request method: {request.method}")
    
    if request.method == 'POST':
        print("POST data received:")
        for key, value in request.POST.items():
            print(f"  {key}: {value}")
        
        staff_id = request.session.get('staff_id')
        print(f"Staff ID from session: {staff_id}")
        
        if not staff_id:
            print("No staff_id in session, redirecting to login")
            return redirect('rental_system:login')
        
        try:
            staff = ManagementStaff.objects.get(id=staff_id)
            print(f"Staff found: {staff.name} (ID: {staff.id})")
            
            # Get form data - only update allowed fields
            new_name = request.POST.get('name', '').strip()
            new_username = request.POST.get('username', '').strip()
            new_phone = request.POST.get('phone', '').strip()
            new_position = request.POST.get('position', '')
            
            # IMPORTANT: Do NOT get email and department from POST
            # Keep the existing values from database
            # new_email is ignored (not updated)
            # new_department is ignored (not updated)
            
            print(f"New name: {new_name}")
            print(f"New username: {new_username}")
            print(f"New phone: {new_phone}")
            print(f"New position: {new_position}")
            print(f"Email remains: {staff.outlook_mail} (not changed)")
            print(f"Department remains: {staff.department} (not changed)")
            
            # Check if username is already taken by another user
            if new_username and new_username != staff.username:
                if ManagementStaff.objects.filter(username=new_username).exclude(id=staff.id).exists():
                    messages.error(request, 'Username already taken. Please choose another.')
                    return redirect('rental_system:profile_settings')
            
            # Update ONLY allowed fields
            if new_name:
                staff.name = new_name
            if new_username:
                staff.username = new_username
            if new_position:
                staff.position = new_position
            if new_phone:
                staff.phone_number = new_phone
            
            # DO NOT update email and department - keep original values
            # staff.outlook_mail remains unchanged
            # staff.department remains unchanged
            
            staff.save()
            print("Staff saved successfully!")
            
            messages.success(request, 'Profile updated successfully!')
            
        except ManagementStaff.DoesNotExist:
            print(f"ERROR: Staff with ID {staff_id} not found!")
            messages.error(request, 'Staff member not found.')
        except Exception as e:
            print(f"ERROR: {str(e)}")
            messages.error(request, f'An error occurred: {str(e)}')
        
        return redirect('rental_system:profile_settings')
    
    return redirect('rental_system:profile_settings')

def change_password(request):
    """Handle password change form submission"""
    print("=" * 50)
    print("CHANGE PASSWORD VIEW CALLED")
    print(f"Request method: {request.method}")
    
    if request.method == 'POST':
        print("POST data received:")
        for key, value in request.POST.items():
            print(f"  {key}: {value}")
        
        staff_id = request.session.get('staff_id')
        print(f"Staff ID from session: {staff_id}")
        
        if not staff_id:
            print("No staff_id in session, redirecting to login")
            messages.error(request, 'Your session has expired. Please login again.')
            return redirect('rental_system:login')
        
        try:
            staff = ManagementStaff.objects.get(id=staff_id)
            print(f"Staff found: {staff.username} (ID: {staff.id})")
            
            current_password = request.POST.get('current_password')
            new_password = request.POST.get('new_password')
            confirm_password = request.POST.get('confirm_password')
            
            print(f"Current password provided: {'Yes' if current_password else 'No'}")
            print(f"New password provided: {'Yes' if new_password else 'No'}")
            print(f"Confirm password provided: {'Yes' if confirm_password else 'No'}")
            
            # Verify current password
            from django.contrib.auth.hashers import check_password
            password_match = check_password(current_password, staff.password)
            print(f"Password match: {password_match}")
            
            if not password_match:
                print("Current password is incorrect")
                messages.error(request, 'Current password is incorrect.')
                return redirect('rental_system:account_settings')
            
            # Verify new passwords match
            if new_password != confirm_password:
                print("New passwords do not match")
                messages.error(request, 'New passwords do not match.')
                return redirect('rental_system:account_settings')
            
            # Verify password strength
            if len(new_password) < 8:
                print("Password too short")
                messages.error(request, 'Password must be at least 8 characters long.')
                return redirect('rental_system:account_settings')
            
            # Update password
            from django.contrib.auth.hashers import make_password
            hashed_password = make_password(new_password)
            print(f"New password hash: {hashed_password[:20]}...")
            
            staff.password = hashed_password
            staff.save()
            print("Password saved successfully!")
            
            messages.success(request, 'Password changed successfully!')
            print("Success message added")
            
        except ManagementStaff.DoesNotExist:
            print(f"ERROR: Staff with ID {staff_id} not found!")
            messages.error(request, 'Staff member not found.')
        except Exception as e:
            print(f"ERROR: {str(e)}")
            messages.error(request, f'An error occurred: {str(e)}')
        
        return redirect('rental_system:account_settings')
    
    print("Not a POST request, redirecting to account_settings")
    return redirect('rental_system:account_settings')

def deactivate_account(request):
    """Handle account deactivation"""
    if request.method == 'GET':
        staff_id = request.session.get('staff_id')
        if not staff_id:
            return redirect('rental_system:login')
        
        try:
            staff = ManagementStaff.objects.get(id=staff_id)
            staff.status = 'Resigned'  # or whatever status you use for inactive
            staff.save()
            
            # Log out the user
            del request.session['staff_id']
            messages.info(request, 'Your account has been deactivated.')
            
        except ManagementStaff.DoesNotExist:
            pass
        
    return redirect('rental_system:login')

def save_preferences(request):
    """Save system preferences"""
    if request.method == 'POST':
        staff_id = request.session.get('staff_id')
        if not staff_id:
            return redirect('rental_system:login')
        
        try:
            # Get all preferences from form
            preferences = {
                'system_name': request.POST.get('system_name', 'UniKit - Laptop Rental System'),
                'company_name': request.POST.get('company_name', 'MIIT'),
                'language': request.POST.get('language', 'en'),
                'date_format': request.POST.get('date_format', 'Y-m-d'),
                'timezone': request.POST.get('timezone', 'Asia/Yangon'),
                'email_notifications': request.POST.get('email_notifications') == 'on',
                'assignment_alerts': request.POST.get('assignment_alerts') == 'on',
                'overdue_alerts': request.POST.get('overdue_alerts') == 'on',
                'daily_summary': request.POST.get('daily_summary') == 'on',
                'notification_email': request.POST.get('notification_email', ''),
                'default_rental_days': request.POST.get('default_rental_days', 14),
                'max_rental_days': request.POST.get('max_rental_days', 30),
                'multiple_rentals': request.POST.get('multiple_rentals') == 'on',
                'auto_serial': request.POST.get('auto_serial') == 'on',
                'serial_prefix': request.POST.get('serial_prefix', 'LP-'),
                'session_timeout': request.POST.get('session_timeout', 30),
                'password_min_length': request.POST.get('password_min_length', 8),
                'strong_password': request.POST.get('strong_password') == 'on',
                'login_attempts': request.POST.get('login_attempts', 5),
                'require_2fa': request.POST.get('require_2fa') == 'on',
                'theme': request.POST.get('theme', 'default'),
                'primary_color': request.POST.get('primary_color', '#5b72b5'),
                'rows_per_page': request.POST.get('rows_per_page', 10),
                'compact_mode': request.POST.get('compact_mode') == 'on',
                'animations': request.POST.get('animations') == 'on',
                'audit_log_retention': request.POST.get('audit_log_retention', 90),
                'auto_backup': request.POST.get('auto_backup') == 'on',
                'backup_frequency': request.POST.get('backup_frequency', 'daily'),
                'export_format': request.POST.get('export_format', 'csv'),
            }
            
            # Here you would save to database
            # For now, just show success message
            messages.success(request, 'System preferences saved successfully!')
            
            # Create audit log
            staff = ManagementStaff.objects.get(id=staff_id)
            AuditLog.objects.create(
                staff=staff,
                action_type='Update',
                target_table='system_preferences',
                record_id='1',
                description='System preferences updated'
            )
            
        except Exception as e:
            messages.error(request, f'Error saving preferences: {str(e)}')
        
        return redirect('rental_system:system_preferences')
    
    return redirect('rental_system:system_preferences')

def is_valid_miit_email(email):
    email = (email or "").strip().lower()
    return email.endswith("@miit.edu.mm") and len(email) > len("@miit.edu.mm")


def _sync_staff_laptop_assignment(staff, selected_laptop_id):
    """
    Keep / change / remove the current active laptop assignment for a staff member.
    Returns the current active laptop object or None.
    """
    today = timezone.now().date()
    selected_laptop_id = (selected_laptop_id or "").strip()

    active_assignment = LaptopAssignment.objects.select_related('laptop').filter(
        person=staff.person,
        assignment_status__in=ACTIVE_ASSIGNMENT_STATUSES,
        actual_return_date__isnull=True,
    ).first()

    current_laptop = active_assignment.laptop if active_assignment else None

    # Keep current laptop as-is
    if selected_laptop_id and current_laptop and str(current_laptop.id) == selected_laptop_id:
        return current_laptop

    # Remove existing assignment if needed
    if active_assignment:
        active_assignment.assignment_status = 'Returned'
        active_assignment.actual_return_date = today
        active_assignment.save()

        current_laptop.status = 'Available'
        current_laptop.for_whom = 'Student'
        current_laptop.save()

    # No new laptop selected
    if not selected_laptop_id:
        return None

    # Assign new laptop
    new_laptop = get_object_or_404(Laptop, pk=selected_laptop_id)

    is_assignable, error_message = validate_laptop_is_assignable(new_laptop)
    if not is_assignable:
        raise ValueError(error_message)

    LaptopAssignment.objects.create(
        person=staff.person,
        laptop=new_laptop,
        issue_date=today,
        expected_return_date=today,
        academic_year=str(today.year),
        assignment_status='Issued',
    )

    new_laptop.status = 'Assigned'
    new_laptop.for_whom = 'Staff'
    new_laptop.save()

    return new_laptop


def staff_list(request):
    refresh_overdue_assignments()

    staff_qs = Staff.objects.select_related('person').all()
    staff_type = (request.GET.get('staff_type') or '').strip()
    unit = (request.GET.get('unit') or '').strip()
    search = (request.GET.get('search') or '').strip()
    sort = (request.GET.get('sort') or 'newest').strip()

    if staff_type:
        staff_qs = staff_qs.filter(staff_type=staff_type)

    if unit:
        staff_qs = staff_qs.filter(
            Q(department=unit) | Q(office_section=unit)
        )

    if search:
        staff_qs = staff_qs.filter(
            Q(person__name__icontains=search) |
            Q(person__outlook_mail__icontains=search) |
            Q(person__phone_number__icontains=search) |
            Q(position__icontains=search)
        )

    if sort == 'oldest':
        staff_qs = staff_qs.order_by('id')
    elif sort == 'az':
        staff_qs = staff_qs.order_by('person__name')
    elif sort == 'za':
        staff_qs = staff_qs.order_by('-person__name')
    else:
        sort = 'newest'
        staff_qs = staff_qs.order_by('-id')

    staff_list_data = list(staff_qs)

    person_ids = [s.person_id for s in staff_list_data]
    active_assignments = LaptopAssignment.objects.select_related('laptop').filter(
        person_id__in=person_ids,
        person__person_type='Staff',
        assignment_status__in=ACTIVE_ASSIGNMENT_STATUSES,
        actual_return_date__isnull=True,
    )
    assignment_map = {a.person_id: a for a in active_assignments}

    for s in staff_list_data:
        s.current_assignment = assignment_map.get(s.person_id)
        s.current_laptop = s.current_assignment.laptop if s.current_assignment else None

    available_laptops = Laptop.objects.filter(status="Available").count()

    return render(request, "staff_list.html", {
        "staff": staff_list_data,
        "staff_types": Staff.STAFF_TYPE_CHOICES,
        "departments": Staff.DEPARTMENT_CHOICES,
        "office_sections": Staff.OFFICE_SECTION_CHOICES,
        "available_laptops": available_laptops,
        "view": request.GET.get("view", "table"),
        "search_query": search,
        "selected_unit": unit,
        "selected_staff_type": staff_type,
        "selected_sort": sort,
        "total_staff": len(staff_list_data),
    })


def staff_create(request):
    if request.method != "POST":
        return redirect('rental_system:staff_list')

    name = (request.POST.get('name') or '').strip()
    outlook_mail = (request.POST.get('outlook_mail') or '').strip()
    phone_number = (request.POST.get('phone_number') or '').strip()
    staff_type = (request.POST.get('staff_type') or '').strip()
    position = (request.POST.get('position') or '').strip()
    staff_status = (request.POST.get('staff_status') or 'Active').strip()
    department = request.POST.get('department') if staff_type == 'Teaching' else None
    office_section = request.POST.get('office_section') if staff_type == 'Office' else None
    selected_laptop_id = request.POST.get('laptop')

    if not is_valid_miit_email(outlook_mail):
        messages.error(request, 'We only accept MIIT Outlook mail (miit.edu.mm).')
        return redirect('rental_system:staff_list')

    try:
        with transaction.atomic():
            person = Person.objects.create(
                name=name,
                outlook_mail=outlook_mail,
                phone_number=phone_number,
                person_type='Staff',
                status='Active'
            )

            staff = Staff.objects.create(
                person=person,
                staff_type=staff_type,
                position=position,
                staff_status=staff_status,
                department=department,
                office_section=office_section,
            )

            _sync_staff_laptop_assignment(staff, selected_laptop_id)

            current_staff_id = request.session.get('staff_id')
            if current_staff_id:
                try:
                    current_staff = ManagementStaff.objects.get(id=current_staff_id)
                    AuditLog.objects.create(
                        staff=current_staff,
                        action_type='Create',
                        target_table='staff',
                        record_id=staff.id,
                        description=f'Created staff: {person.name}'
                    )
                except ManagementStaff.DoesNotExist:
                    pass

        messages.success(request, 'Staff created successfully!')
    except ValueError as e:
        messages.error(request, str(e))
    except Exception as e:
        messages.error(request, f'Could not create staff. {str(e)}')

    return redirect('rental_system:staff_list')


def staff_update(request, pk):
    staff = get_object_or_404(Staff.objects.select_related('person'), pk=pk)

    if request.method != "POST":
        return redirect('rental_system:staff_list')

    person = staff.person

    old_name = person.name or ''
    old_email = person.outlook_mail or ''
    old_phone = person.phone_number or ''
    old_staff_type = staff.staff_type or ''
    old_position = staff.position or ''
    old_status = staff.staff_status or ''
    old_department = staff.department or ''
    old_office_section = staff.office_section or ''

    old_assignment = LaptopAssignment.objects.select_related('laptop').filter(
        person=person,
        assignment_status__in=ACTIVE_ASSIGNMENT_STATUSES,
        actual_return_date__isnull=True,
    ).first()
    old_laptop_id = str(old_assignment.laptop.id) if old_assignment and old_assignment.laptop else ''
    old_laptop_serial = old_assignment.laptop.SerialNumber if old_assignment and old_assignment.laptop else 'None'

    new_name = (request.POST.get('name') or '').strip()
    new_email = (request.POST.get('outlook_mail') or '').strip()
    new_phone = (request.POST.get('phone_number') or '').strip()
    new_staff_type = (request.POST.get('staff_type') or '').strip()
    new_position = (request.POST.get('position') or '').strip()
    new_status = (request.POST.get('staff_status') or staff.staff_status or 'Active').strip()
    new_department = request.POST.get('department') if new_staff_type == 'Teaching' else None
    new_office_section = request.POST.get('office_section') if new_staff_type == 'Office' else None
    selected_laptop_id = (request.POST.get('laptop') or '').strip()

    if not is_valid_miit_email(new_email):
        messages.error(request, 'We only accept MIIT Outlook mail (miit.edu.mm).')
        return redirect('rental_system:staff_list')

    changes = []

    if old_name != new_name:
        changes.append(f"Name: '{old_name}' → '{new_name}'")
    if old_email != new_email:
        changes.append(f"Email: '{old_email}' → '{new_email}'")
    if old_phone != new_phone:
        changes.append(f"Phone: '{old_phone or '—'}' → '{new_phone or '—'}'")
    if old_staff_type != new_staff_type:
        changes.append(f"Type: '{old_staff_type}' → '{new_staff_type}'")
    if old_position != new_position:
        changes.append(f"Position: '{old_position}' → '{new_position}'")
    if old_status != new_status:
        changes.append(f"Status: '{old_status}' → '{new_status}'")
    if old_department != (new_department or ''):
        changes.append(f"Department: '{old_department or '—'}' → '{new_department or '—'}'")
    if old_office_section != (new_office_section or ''):
        changes.append(f"Office Section: '{old_office_section or '—'}' → '{new_office_section or '—'}'")

    normalized_selected_laptop = selected_laptop_id or ''
    if old_laptop_id != normalized_selected_laptop:
        new_laptop_label = 'None'
        if normalized_selected_laptop:
            try:
                new_laptop_label = Laptop.objects.get(id=normalized_selected_laptop).SerialNumber
            except Laptop.DoesNotExist:
                new_laptop_label = 'Unknown'
        changes.append(f"Laptop: '{old_laptop_serial}' → '{new_laptop_label}'")

    if not changes:
        return redirect('rental_system:staff_list')

    try:
        with transaction.atomic():
            person.name = new_name
            person.outlook_mail = new_email
            person.phone_number = new_phone
            person.save()

            staff.staff_type = new_staff_type
            staff.position = new_position
            staff.staff_status = new_status
            staff.department = new_department
            staff.office_section = new_office_section
            staff.save()

            _sync_staff_laptop_assignment(staff, selected_laptop_id)

            current_staff_id = request.session.get('staff_id')
            if current_staff_id:
                try:
                    current_staff = ManagementStaff.objects.get(id=current_staff_id)
                    AuditLog.objects.create(
                        staff=current_staff,
                        action_type='Update',
                        target_table='staff',
                        record_id=staff.id,
                        description=f"Updated staff: {person.name}. " + "; ".join(changes)
                    )
                except ManagementStaff.DoesNotExist:
                    pass

        messages.success(request, 'Staff updated successfully!')
    except ValueError as e:
        messages.error(request, str(e))
    except Exception as e:
        messages.error(request, f'Could not update staff. {str(e)}')

    return redirect('rental_system:staff_list')

def import_staff_excel(request):
    if request.method != 'POST':
        return redirect('rental_system:staff_list')

    file = request.FILES.get('file')
    if not file:
        messages.error(request, "Please choose an Excel file.")
        return redirect('rental_system:staff_list')

    try:
        df = pd.read_excel(file)
    except Exception:
        messages.error(request, "Could not read the Excel file.")
        return redirect('rental_system:staff_list')

    required_columns = [
        'name',
        'outlook_mail',
        'phone_number',
        'staff_type',
        'position',
        'department',
        'office_section',
        'laptop',
    ]

    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        messages.error(
            request,
            "Missing required columns: " + ", ".join(missing_columns)
        )
        return redirect('rental_system:staff_list')

    imported_count = 0

    for _, row in df.iterrows():
        outlook_mail = str(row.get('outlook_mail', '')).strip()
        if not outlook_mail:
            continue

        name = str(row.get('name', '')).strip()
        phone_number = str(row.get('phone_number', '')).strip()
        staff_type = str(row.get('staff_type', '')).strip()
        position = str(row.get('position', '')).strip()
        department = str(row.get('department', '')).strip()
        office_section = str(row.get('office_section', '')).strip()
        laptop_serial = str(row.get('laptop', '')).strip()

        if staff_type not in ['Teaching', 'Office']:
            staff_type = 'Office'

        if staff_type == 'Teaching':
            office_section = ''
        else:
            department = ''

        laptop_obj = None
        if laptop_serial:
            laptop_obj = Laptop.objects.filter(SerialNumber=laptop_serial).first()

        person, _ = Person.objects.update_or_create(
            outlook_mail=outlook_mail,
            defaults={
                'name': name,
                'phone_number': phone_number,
                'person_type': 'Staff',
            }
        )

        Staff.objects.update_or_create(
            person=person,
            defaults={
                'staff_type': staff_type,
                'position': position,
                'department': department if department else None,
                'office_section': office_section if office_section else None,
                'laptop': laptop_obj,
                'staff_status': 'Active',
            }
        )

        imported_count += 1

    messages.success(request, f"{imported_count} staff imported successfully!")
    return redirect('rental_system:staff_list')

def assign_new_admin(request):
    """
    View for creating new admin/staff management accounts.
    Any logged-in admin can create new admin accounts.
    """
    # Check if user is logged in
    staff_id = request.session.get('staff_id')
    if not staff_id:
        messages.error(request, 'Please login to access this page.')
        return redirect('rental_system:login')
    
    try:
        current_staff = ManagementStaff.objects.get(id=staff_id)
        # Check if staff is active
        if current_staff.status != 'Active':
            messages.error(request, 'Your account is not active. Please contact administrator.')
            return redirect('rental_system:login')
    except ManagementStaff.DoesNotExist:
        messages.error(request, 'Staff member not found.')
        return redirect('rental_system:login')
    
    if request.method == 'POST':
        # Get form data
        name = request.POST.get('name', '').strip()
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip().lower()  # Convert to lowercase
        phone = request.POST.get('phone', '').strip()
        position = request.POST.get('position', '')
        department = request.POST.get('department', '')
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')
        send_notification = request.POST.get('send_notification') == 'yes'
        
        # Store form data for repopulation on error
        form_data = {
            'name': name,
            'username': username,
            'email': email,
            'phone': phone,
            'position': position,
            'department': department,
            'send_notification': send_notification
        }
        
        # Initialize errors list
        errors = []
        
        # Check required fields
        if not name:
            errors.append("Full name is required.")
        if not username:
            errors.append("Username is required.")
        if not email:
            errors.append("Email address is required.")
        if not position:
            errors.append("Position is required.")
        if not department:
            errors.append("Department is required.")
        if not password:
            errors.append("Password is required.")
        if not confirm_password:
            errors.append("Please confirm your password.")
        
        # Validate MIIT email format (using the is_valid_miit_email function)
        if email and not is_valid_miit_email(email):
            errors.append("Only MIIT email addresses (@miit.edu.mm) are allowed. Please use your university email.")
        
        # Check if username already exists
        if username and ManagementStaff.objects.filter(username=username).exists():
            errors.append(f"Username '{username}' is already taken. Please choose another one.")
        
        # Check if email already exists
        if email and ManagementStaff.objects.filter(outlook_mail__iexact=email).exists():
            errors.append(f"Email '{email}' is already registered. Please use a different email.")
        
        # Validate email format
        if email and not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            errors.append("Please enter a valid email address.")
        
        # Validate phone number (optional)
        if phone and not re.match(r'^[0-9\-+]{9,15}$', phone):
            errors.append("Phone number should contain only numbers, dashes, and plus sign (9-15 characters).")
        
        # Check password match
        if password and confirm_password and password != confirm_password:
            errors.append("Passwords do not match.")
        
        # Validate password strength
        if password and len(password) < 6:
            errors.append("Password must be at least 6 characters long.")
        
        # If there are errors, return to form with error messages
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'assign_new_admin.html', {'form_data': form_data})
        
        # Create new management staff account
        try:
            from django.contrib.auth.hashers import make_password
            
            # DEBUG: Print the password being hashed
            print("=" * 50)
            print("CREATING NEW ADMIN ACCOUNT")
            print(f"Name: {name}")
            print(f"Username: {username}")
            print(f"Email: {email}")
            print(f"Plain password: {password}")
            
            # Hash the password
            hashed_password = make_password(password)
            print(f"Hashed password: {hashed_password}")
            
            # Create the new admin/staff account
            new_admin = ManagementStaff.objects.create(
                name=name,
                username=username,
                outlook_mail=email,
                phone_number=phone if phone else None,
                position=position,
                department=department,
                password=hashed_password,
                status='Active',
            )
            
            print(f"Account created successfully! ID: {new_admin.id}")
            print(f"Stored password in DB: {new_admin.password}")
            
            # Verify the password was stored correctly
            from django.contrib.auth.hashers import check_password
            verification = check_password(password, new_admin.password)
            print(f"Password verification test: {verification}")
            print("=" * 50)
            
            # Create audit log for this action
            try:
                AuditLog.objects.create(
                    staff=current_staff,
                    action_type='Insert',
                    target_table='management_staff',
                    record_id=new_admin.id,
                    old_value='',
                    new_value=f"Created new staff: {name} (Username: {username}, Position: {position}, Department: {department})",
                    description=f"Created account for {name}"
                )
            except Exception as audit_error:
                print(f"Audit log error: {audit_error}")
            
            # Send email notification if requested
            if send_notification and email:
                try:
                    from django.core.mail import send_mail
                    from django.conf import settings
                    
                    subject = f"Welcome to UniKit - Your Account"
                    message = f"""
Dear {name},

Your account has been created in the UniKit Laptop Rental System.

Account Details:
-----------------
Full Name: {name}
Username: {username}
Email: {email}
Position: {position}
Department: {department}
Phone: {phone if phone else 'Not provided'}

Temporary Login Password: {password}

**Important Security Notes:**
1. Please change your password after your first login.
2. Keep your credentials secure and do not share them.
3. If you didn't request this account, please contact the system administrator immediately.

Login URL: {request.build_absolute_uri('/login/')}

Best regards,
UniKit Administration Team
{current_staff.name}
"""
                    
                    send_mail(
                        subject,
                        message,
                        settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'noreply@unikit.edu.mm',
                        [email],
                        fail_silently=True,
                    )
                    messages.success(request, f"Account created successfully! A welcome email has been sent to {email}.")
                except Exception as email_error:
                    messages.success(request, f"Account created successfully! However, email notification could not be sent.")
            else:
                messages.success(request, f"Account for {name} has been created successfully!")
            
            return redirect('rental_system:home')
            
        except Exception as e:
            print(f"ERROR creating account: {str(e)}")
            messages.error(request, f"An error occurred while creating the account: {str(e)}")
            return render(request, 'assign_new_admin.html', {'form_data': form_data})
    
    # GET request - display empty form
    return render(request, 'assign_new_admin.html')

def is_valid_miit_email(email):
    """Validate that email ends with @miit.edu.mm"""
    email = (email or "").strip().lower()
    return email.endswith("@miit.edu.mm") and len(email) > len("@miit.edu.mm")

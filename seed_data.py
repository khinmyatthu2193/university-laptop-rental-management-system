exec("""
from rental_system.models import Person, Student, Staff, Laptop

student_first_names = [
    "Aung", "Thiri", "Mya", "Kyaw", "Su", "Hnin", "Zin", "Phyo", "Htut", "May",
    "Nyein", "Ei", "Yadanar", "Khant", "Aye", "Soe", "Thu", "Khin", "Wai", "Nan"
]
student_last_names = ["Min", "Oo", "Tun", "Hlaing", "Win"]

staff_first_names = [
    "Aung", "Mya", "Kyaw", "Su", "Hla", "Khin", "Soe", "Ei", "Min", "Thiri",
    "Zaw", "Hnin", "Tun", "May", "Phyo", "Aye", "Khant", "Nan", "Wai", "Zin"
]
staff_last_names = ["Aung", "Myint", "Soe", "Tun", "Win"]

majors = ["CSE", "ECE"]
teaching_departments = ["FCST", "FCS", "FIS", "ITSM", "FC", "NS", "Eng", "Myanmar"]
teaching_positions = ["Professor", "Associate Professor", "Lecturer", "Assistant Lecturer", "Tutor"]
office_sections = ["Management", "Student Affair", "Library", "Financial and Accounting"]
office_positions = ["Manager", "Senior Assistant", "Assistant", "Officer", "Clerk"]

# -----------------------------
# 1) Create 100 laptops
# Same specification, only serial number changes
# -----------------------------
for i in range(1, 101):
    Laptop.objects.update_or_create(
        SerialNumber=f"LP{i:03d}",
        defaults={
            "name": "Vivo Book",
            "brand": "HP",
            "processor_gen": "i4 7th gen",
            "ram": 4,
            "storage": "256 Gb",
            "for_whom": "Staff",
            "status": "Available",
            "remark": "",
        }
    )

# -----------------------------
# 2) Create 100 students
# -----------------------------
for i in range(1, 101):
    first = student_first_names[(i - 1) % len(student_first_names)]
    last = student_last_names[((i - 1) // len(student_first_names)) % len(student_last_names)]
    full_name = f"{first} {last}"

    Student.objects.update_or_create(
        student_id=f"STU{i:03d}",
        defaults={
            "full_name": full_name,
            "email": f"student{i:03d}@miit.edu.mm",
            "phone": f"09{770000000 + i}",
            "major": majors[(i - 1) % len(majors)],
            "batch_year": 2021 + ((i - 1) % 5),
            "laptop": None,
        }
    )

# -----------------------------
# 3) Create 100 staff
# Staff requires Person first
# -----------------------------
for i in range(1, 101):
    first = staff_first_names[(i - 1) % len(staff_first_names)]
    last = staff_last_names[((i - 1) // len(staff_first_names)) % len(staff_last_names)]
    staff_name = f"{first} {last}"
    email = f"staff{i:03d}@miit.edu.mm"

    person, _ = Person.objects.update_or_create(
        outlook_mail=email,
        defaults={
            "name": staff_name,
            "phone_number": f"09{880000000 + i}",
            "person_type": "Staff",
            "status": "Active",
        }
    )

    if i <= 60:
        Staff.objects.update_or_create(
            person=person,
            defaults={
                "staff_type": "Teaching",
                "position": teaching_positions[(i - 1) % len(teaching_positions)],
                "phone_no": f"09{880000000 + i}",
                "laptop": None,
                "staff_status": "Active",
                "department": teaching_departments[(i - 1) % len(teaching_departments)],
                "office_section": None,
            }
        )
    else:
        office_index = i - 61
        Staff.objects.update_or_create(
            person=person,
            defaults={
                "staff_type": "Office",
                "position": office_positions[office_index % len(office_positions)],
                "phone_no": f"09{880000000 + i}",
                "laptop": None,
                "staff_status": "Active",
                "department": None,
                "office_section": office_sections[office_index % len(office_sections)],
            }
        )

print("Done")
print("Students:", Student.objects.count())
print("Persons:", Person.objects.count())
print("Staff:", Staff.objects.count())
print("Laptops:", Laptop.objects.count())
""")
# UniKit — University Laptop Rental Management System

UniKit is a Django web application for managing university laptop inventory, student and staff records, assignments, returns, and repairs. Developed at the **Myanmar Institute of Information Technology (MIIT)**, it brings laptop rental records into a centralized system to reduce paperwork, improve accuracy, and help staff track availability and laptop condition.

## Project background

Laptops are essential for university study, but not every student can afford a personal device. Universities provide rental laptops, while manual records in paper files and spreadsheets can make approvals slow and availability, return dates, and maintenance difficult to track.

UniKit aims to:

- Replace manual rental processes with a centralized digital workflow.
- Maintain up-to-date laptop inventory and assignment records.
- Track issue dates, expected returns, and overdue assignments.
- Record laptop condition and maintenance history.
- Reduce administrative workload and support timely access to laptops.
- Support management decision-making through reporting as the system develops.

## Core modules

The final semester presentation identifies six implemented modules:

| Module | Capabilities |
| --- | --- |
| User authentication | Management staff signup, login, and logout |
| Student management | Register, view, update, search, and filter student records |
| Staff management | Register, view, update, search, and filter teaching and office staff records |
| Inventory management | Register laptops, update specifications, and track availability and status |
| Assignment management | Assign laptops, view assignment status, and prevent duplicate active assignments |
| Data management and validation | Validate input and maintain organized, editable records |

The current repository also includes return processing, overdue status updates, repair issue tracking, Excel imports for students/staff/laptops, dashboard summaries, account settings, and an audit log page. Laptop statuses include `Available`, `Assigned`, `In Repair`, and `Damage`; assignment statuses include `Issued`, `Returned`, and `Overdue`.

## Typical workflow

1. Register a management account and log in.
2. Add or import student, staff, and laptop records.
3. Assign an available laptop to a student or staff member.
4. Review active assignments and expected return dates.
5. Process returns and record the laptop's condition; track repair issues when needed.
6. Review inventory, dashboard summaries, and recorded audit activity.

## Technology stack

| Layer | Technology |
| --- | --- |
| Backend | Python and Django 6.0 |
| Database | SQLite (default local configuration) |
| Frontend | Django templates, HTML, CSS, JavaScript, and Bootstrap |
| Spreadsheet imports | pandas and openpyxl |

Dependency ranges are defined in [requirements.txt](requirements.txt).

## Local setup

Run the following commands from the directory containing `manage.py`. Use Python 3.12 or newer for Django 6.0.

1. Create a virtual environment:

   ```bash
   python -m venv .venv
   ```

2. Activate it:

   Windows PowerShell:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

   macOS / Linux:

   ```bash
   source .venv/bin/activate
   ```

3. Install dependencies and apply database migrations:

   ```bash
   python -m pip install -r requirements.txt
   python manage.py migrate
   ```

4. Optionally populate a development database with sample records:

   ```bash
   python manage.py shell -c "exec(open('seed_data.py', encoding='utf-8').read())"
   ```

   The script creates or updates 100 laptops, 100 students, and 100 staff records. It must run inside Django's initialized environment. Use it on a sample database: rerunning it overwrites matching sample records, including laptop statuses and student/staff laptop links. It does not create a management login.

5. Start the development server:

   ```bash
   python manage.py runserver
   ```

6. Open <http://127.0.0.1:8000/>. Create a management account at <http://127.0.0.1:8000/home/signin/> using an `@miit.edu.mm` email address, then use <http://127.0.0.1:8000/home/login/> for subsequent logins. The application dashboard is at <http://127.0.0.1:8000/home/>.

Application accounts use the `ManagementStaff` model. Django's separate `/admin/` interface uses a Django superuser, which can optionally be created with `python manage.py createsuperuser`.

## Project structure

```text
.
├── manage.py
├── requirements.txt
├── seed_data.py
├── rental_system/
│   ├── models.py          # Inventory, people, assignments, repairs, and audit data
│   ├── views.py           # Application workflows and request handlers
│   ├── forms.py           # Student and laptop forms
│   ├── urls.py            # Application routes under /home/
│   ├── migrations/       # Database schema history
│   ├── templates/        # Application pages
│   └── templatetags/      # Template helpers
└── unikit_university_laptop_rental_management_system/
    ├── settings.py        # Django configuration
    └── urls.py            # Landing page, application, and admin routes
```

## Future development

The April 2026 presentation lists overdue tracking, report generation, advanced dashboard analytics, PDF/Excel exports, notifications and reminders, UI improvements, and advanced security as future extensions.

Since that presentation, the current code includes overdue tracking and dashboard summaries. The remaining roadmap items should be treated as planned enhancements; Excel import support does not imply Excel export support.

## Academic context and credits

This README draws on *UniKit: University Laptop Rental Management System — Final Semester Presentation*, presented on **2 April 2026** for **Computer Science and Engineering, I Semester 2025–2026**, at MIIT. Implementation details and setup instructions reflect the current repository.

The presentation describes use case, workflow, and entity-relationship diagrams, along with an Agile prototype approach for iterative feedback and validation. Learning outcomes include Django development, authentication and access control, database design, system analysis, testing and debugging, teamwork, and presentation skills.

**Instructor-in-charge:** Dr. Myat Thuzar Htun

**Project supervisor:** Daw Moe Thida

| Team member | Student ID |
| --- | --- |
| Mg Shine Aung Lwin | 2019-MIIT-CSE-049 |
| Ma Khin Myat Thu | 2021-MIIT-CSE-020 |
| Ma Nandar Kyaw | 2021-MIIT-CSE-045 |

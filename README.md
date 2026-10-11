# UniKit

**University Laptop Rental Management System** is a Django application for managing university laptop inventory and rentals at the Myanmar Institute of Information Technology (MIIT). It helps staff keep student and staff records, laptop assignments, returns, repairs, and account access in one place.

## What it does

- Manage student, staff, and laptop records, including Excel imports.
- Assign laptops and track expected return dates, returns, and overdue rentals.
- Record repair issues and laptop condition.
- View inventory and dashboard summaries, and review audit activity.
- Create UniKit staff accounts and grant access by operational area.

Laptop states include `Available`, `Assigned`, `In Repair`, and `Damage`. Active assignments use `Issued` or `Overdue`; completed assignments use `Returned`.

## Requirements

- Python 3.12 or newer
- Windows, macOS, or Linux for local development
- Python dependencies listed in [requirements.txt](requirements.txt)

The default database is SQLite (`db.sqlite3`). The production launcher and backup scripts described below are PowerShell scripts for Windows.

## Run locally

From the project directory containing `manage.py`:

```bash
python -m venv .venv
```

Activate the environment:

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

```bash
# macOS or Linux
source .venv/bin/activate
```

Install dependencies, create the database schema, and start the development server:

```bash
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Open <http://127.0.0.1:8000/>. For a new development database, create the initial management account at <http://127.0.0.1:8000/home/signin/> with an `@miit.edu.mm` email address. Sign in at <http://127.0.0.1:8000/home/login/>; the dashboard is at <http://127.0.0.1:8000/home/>.

To load optional sample data, stop the server and run:

```bash
python manage.py shell -c "exec(open('seed_data.py', encoding='utf-8').read())"
```

This creates or updates 100 laptops, 100 students, and 100 staff records. It does not create a login. Rerunning it overwrites matching sample records, including laptop statuses and student or staff laptop links, so use it only with a development database.

Django admin at `/admin/` is separate from UniKit accounts and requires a Django superuser. Create one with `python manage.py createsuperuser` if needed.

## Run on a single Windows laptop

The production setup is intended for local access on one Windows computer. Waitress listens on `127.0.0.1:8080`; other computers cannot connect. Do not expose the service to a network without first adding HTTPS and reviewing the security settings.

1. Create a clean Python environment and install dependencies. An old `venv/` folder may reference a Python installation that no longer exists.

   ```powershell
   python --version
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```

2. Set a private Django key for your Windows user. Open a new PowerShell window afterward. Keep the key out of Git and do not share it.

   ```powershell
   $secret = python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
   [Environment]::SetEnvironmentVariable("DJANGO_SECRET_KEY", $secret, "User")
   ```

3. Start UniKit:

   ```powershell
   .\scripts\start_unikit.ps1
   ```

   The script applies migrations, collects static files, and starts Waitress. Open <http://127.0.0.1:8080/>. Existing management accounts keep their passwords after migration. On a fresh database, `/home/signin/` creates the first system administrator and then closes public registration.

### UniKit accounts and access

Application accounts are managed in UniKit; they are not Django admin accounts. The protected `daw_moe_thida` owner account has full access, including ITSM account administration. Other ITSM accounts can be granted no access, view-only, or view-and-manage access by operational area through **ITSM User Access**.

New accounts and accounts with a reset password must change their temporary password after signing in before accessing operational areas. Account creation does not email or log plaintext passwords; provide temporary passwords through a separate trusted channel.

### Backups and restore

Store backups on a separate drive or device. Set the destination and run the backup script:

```powershell
[Environment]::SetEnvironmentVariable("UNIKIT_BACKUP_DIR", "E:\UniKit Backups", "User")
.\scripts\backup_unikit.ps1
```

The script uses SQLite's online backup API, runs an integrity check, writes a SHA-256 checksum, and retains the newest 30 backups. Schedule it daily in Windows Task Scheduler while the backup device is available.

To restore, stop UniKit, make a final backup if the current database is readable, verify the chosen backup's checksum, and copy it to `db.sqlite3`. Restart UniKit and check login, inventory, active assignments, and recent audit entries. Practice the restore using a copy of the project before relying on it for official records.

### Production checks

After an update, run:

```powershell
$env:DJANGO_SETTINGS_MODULE = "unikit_university_laptop_rental_management_system.production"
python manage.py check --deploy
python manage.py test
```

The local HTTP deployment does not enable HTTPS-only cookies or HSTS. These must be configured before making UniKit accessible over a LAN or the internet.

## Project layout

```text
manage.py
requirements.txt
seed_data.py
scripts/
  start_unikit.ps1
  backup_unikit.ps1
rental_system/
  models.py       # Inventory, people, assignments, repairs, and audit records
  views.py        # Application workflows
  forms.py        # Forms
  urls.py         # Routes under /home/
  migrations/     # Database schema history
  templates/      # Application pages
unikit_university_laptop_rental_management_system/
  settings.py
  production.py
  urls.py
```

## Project background and credits

UniKit was developed as a final-semester project for Computer Science and Engineering, I Semester 2025–2026, at MIIT. The project presentation was delivered on 2 April 2026. It describes the system workflows, data model, iterative prototype approach, and learning outcomes.

**Instructor-in-charge:** Dr. Myat Thuzar Htun

**Project supervisor:** Daw Moe Thida

| Team member | Student ID |
| --- | --- |
| Mg Shine Aung Lwin | 2019-MIIT-CSE-049 |
| Ma Khin Myat Thu | 2021-MIIT-CSE-020 |
| Ma Nandar Kyaw | 2021-MIIT-CSE-045 |

## Roadmap

Overdue tracking and dashboard summaries are implemented. Report generation, Excel or PDF exports, notifications, reminders, and further interface and security improvements remain possible future work. The existing Excel feature imports records; it does not export them.
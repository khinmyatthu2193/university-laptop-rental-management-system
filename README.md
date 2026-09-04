# University Laptop Rental Management System

A Django application for managing university laptop inventory, assignments, returns, repairs, staff, students, and audit logs.

## Local setup

1. Create and activate a Python virtual environment.
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Apply database migrations:

   ```bash
   python manage.py migrate
   ```

4. Optionally load the sample data:

   ```bash
   python seed_data.py
   ```

5. Start the development server:

   ```bash
   python manage.py runserver
   ```


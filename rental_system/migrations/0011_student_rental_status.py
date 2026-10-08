from django.db import migrations, models


def initialize_rental_status(apps, schema_editor):
    Student = apps.get_model('rental_system', 'Student')
    Student.objects.filter(laptop__isnull=False).update(rental_status='Assigned')


class Migration(migrations.Migration):

    dependencies = [
        ('rental_system', '0010_laptopassignment_legacy_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='student',
            name='rental_status',
            field=models.CharField(
                choices=[
                    ('Not Requested', 'Not Requested'),
                    ('Assigned', 'Assigned'),
                    ('Returned', 'Returned'),
                ],
                default='Not Requested',
                max_length=20,
            ),
        ),
        migrations.RunPython(initialize_rental_status, migrations.RunPython.noop),
    ]

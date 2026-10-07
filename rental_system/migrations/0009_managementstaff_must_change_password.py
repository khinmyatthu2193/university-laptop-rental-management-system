from django.db import migrations, models


def require_existing_staff_password_change(apps, schema_editor):
    ManagementStaff = apps.get_model('rental_system', 'ManagementStaff')
    ManagementStaff.objects.exclude(username__iexact='daw_moe_thida').update(
        must_change_password=True
    )


class Migration(migrations.Migration):
    dependencies = [('rental_system', '0008_managementstaff_permissions')]

    operations = [
        migrations.AddField(
            model_name='managementstaff',
            name='must_change_password',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(
            require_existing_staff_password_change,
            migrations.RunPython.noop,
        ),
    ]

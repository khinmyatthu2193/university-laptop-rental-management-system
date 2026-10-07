from django.db import migrations, models


ALL_PERMISSIONS = [
    'dashboard.view',
    'students.view', 'students.manage',
    'staff_records.view', 'staff_records.manage',
    'inventory.view', 'inventory.manage',
    'assignments.view', 'assignments.manage',
    'returns.view', 'returns.manage',
    'issues.view', 'issues.manage',
    'audit_logs.view',
    'system_preferences.view', 'system_preferences.manage',
]


def establish_owner(apps, schema_editor):
    ManagementStaff = apps.get_model('rental_system', 'ManagementStaff')
    ManagementStaff.objects.exclude(username__iexact='daw_moe_thida').update(
        role='Admin', permissions=[]
    )
    ManagementStaff.objects.filter(username__iexact='daw_moe_thida').update(
        role='SystemAdmin', permissions=ALL_PERMISSIONS
    )


class Migration(migrations.Migration):
    dependencies = [('rental_system', '0007_one_active_assignment_per_person')]

    operations = [
        migrations.AddField(
            model_name='managementstaff',
            name='permissions',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(establish_owner, migrations.RunPython.noop),
    ]

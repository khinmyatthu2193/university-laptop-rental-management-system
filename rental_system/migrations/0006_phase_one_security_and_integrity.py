from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def migrate_management_accounts(apps, schema_editor):
    ManagementStaff = apps.get_model('rental_system', 'ManagementStaff')
    User = apps.get_model('auth', 'User')

    for staff in ManagementStaff.objects.all().order_by('id'):
        user, _ = User.objects.get_or_create(username=staff.username)
        user.email = staff.outlook_mail
        user.first_name = staff.name[:150]
        user.password = staff.password
        user.is_active = staff.status == 'Active'
        user.save(update_fields=['email', 'first_name', 'password', 'is_active'])

        staff.auth_user_id = user.id
        staff.role = 'SystemAdmin'
        staff.save(update_fields=['auth_user', 'role'])


def restore_password_hashes(apps, schema_editor):
    ManagementStaff = apps.get_model('rental_system', 'ManagementStaff')
    for staff in ManagementStaff.objects.select_related('auth_user'):
        staff.password = staff.auth_user.password
        staff.save(update_fields=['password'])


def normalize_assignment_dates(apps, schema_editor):
    LaptopAssignment = apps.get_model('rental_system', 'LaptopAssignment')
    for assignment in LaptopAssignment.objects.filter(
        expected_return_date__lt=models.F('issue_date'),
    ):
        assignment.expected_return_date = assignment.issue_date
        assignment.save(update_fields=['expected_return_date'])


class Migration(migrations.Migration):

    dependencies = [
        ('rental_system', '0005_staff_laptop_staff_phone_no_alter_laptop_storage'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='managementstaff',
            name='auth_user',
            field=models.OneToOneField(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='management_profile',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='managementstaff',
            name='role',
            field=models.CharField(
                choices=[
                    ('SystemAdmin', 'System administrator'),
                    ('Admin', 'Administrator'),
                    ('ReadOnly', 'Read-only reporter'),
                ],
                default='Admin',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='managementstaff',
            name='outlook_mail',
            field=models.EmailField(max_length=254, unique=True),
        ),
        migrations.RunPython(migrate_management_accounts, restore_password_hashes),
        migrations.RemoveField(
            model_name='managementstaff',
            name='password',
        ),
        migrations.AlterField(
            model_name='managementstaff',
            name='auth_user',
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='management_profile',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name='auditlog',
            name='action_type',
            field=models.CharField(
                choices=[
                    ('Create', 'Create'),
                    ('Insert', 'Insert'),
                    ('Update', 'Update'),
                    ('Delete', 'Delete'),
                ],
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='auditlog',
            name='staff',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='rental_system.managementstaff'),
        ),
        migrations.AlterField(
            model_name='blacklist',
            name='person',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='rental_system.person'),
        ),
        migrations.AlterField(
            model_name='damagereport',
            name='assignment',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='rental_system.laptopassignment'),
        ),
        migrations.AlterField(
            model_name='damagereport',
            name='laptop',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='rental_system.laptop'),
        ),
        migrations.AlterField(
            model_name='laptopassignment',
            name='laptop',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='rental_system.laptop'),
        ),
        migrations.AlterField(
            model_name='laptopassignment',
            name='person',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='rental_system.person'),
        ),
        migrations.AlterField(
            model_name='laptopreplacement',
            name='assignment',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='rental_system.laptopassignment'),
        ),
        migrations.AlterField(
            model_name='laptopreplacement',
            name='new_laptop',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='new_laptop',
                to='rental_system.laptop',
            ),
        ),
        migrations.AlterField(
            model_name='laptopreplacement',
            name='old_laptop',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='old_laptop',
                to='rental_system.laptop',
            ),
        ),
        migrations.AlterField(
            model_name='repairlog',
            name='laptop',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='rental_system.laptop'),
        ),
        migrations.AlterField(
            model_name='repairlog',
            name='repair_cost',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.RunPython(normalize_assignment_dates, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='laptopassignment',
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    ('actual_return_date__isnull', True),
                    ('assignment_status__in', ['Issued', 'Overdue']),
                ),
                fields=('laptop',),
                name='one_active_assignment_per_laptop',
            ),
        ),
        migrations.AddConstraint(
            model_name='laptopassignment',
            constraint=models.CheckConstraint(
                condition=models.Q(('expected_return_date__gte', models.F('issue_date'))),
                name='assignment_due_on_or_after_issue',
            ),
        ),
        migrations.AddConstraint(
            model_name='laptopassignment',
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ('actual_return_date__isnull', True),
                    ('actual_return_date__gte', models.F('issue_date')),
                    _connector='OR',
                ),
                name='assignment_return_on_or_after_issue',
            ),
        ),
        migrations.CreateModel(
            name='SystemPreference',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('values', models.JSONField(default=dict)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('updated_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='rental_system.managementstaff')),
            ],
            options={'db_table': 'system_preference'},
        ),
    ]

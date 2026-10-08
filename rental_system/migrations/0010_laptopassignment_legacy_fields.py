from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rental_system', '0009_managementstaff_must_change_password'),
    ]

    operations = [
        migrations.AddField(
            model_name='laptopassignment',
            name='legacy_sign',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='laptopassignment',
            name='remark',
            field=models.TextField(blank=True, default=''),
        ),
    ]

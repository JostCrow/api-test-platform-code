# Generated by Django 2.2.4 on 2019-11-05 11:27

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('servervalidation', '0093_auto_20191101_1643'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='api',
            options={'permissions': (('create_scenario_for_api', 'Create a test scenario for this API'), ('update_scenario_for_api', 'Update a test scenario for this API'), ('delete_scenario_for_api', 'Delete a test scenario for this API'))},
        ),
    ]

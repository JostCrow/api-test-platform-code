# Generated by Django 2.2a1 on 2019-02-05 14:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('testsession', '0053_auto_20190128_1223'),
    ]

    operations = [
        migrations.AddField(
            model_name='session',
            name='build_version',
            field=models.TextField(blank=True, default=None, null=True),
        ),
    ]

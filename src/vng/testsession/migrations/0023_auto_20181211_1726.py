# -*- coding: utf-8 -*-
# Generated by Django 1.11.16 on 2018-12-11 16:26
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('testsession', '0022_auto_20181210_1546'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='scenariocase',
            options={'ordering': ('order',)},
        ),
        migrations.AddField(
            model_name='scenariocase',
            name='order',
            field=models.PositiveIntegerField(db_index=True, default=1, editable=False),
            preserve_default=False,
        ),
    ]

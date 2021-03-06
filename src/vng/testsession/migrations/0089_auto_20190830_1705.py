# Generated by Django 2.2.4 on 2019-08-30 15:05

from django.db import migrations


def set_order(apps, schema_editor):
    SessionType = apps.get_model('testsession', 'SessionType')
    for sessiontype in SessionType.objects.all():
        i = 0
        for endpoint in sessiontype.vngendpoint_set.all():
            endpoint.order = i
            endpoint.save()
            i += 1



def remove_order(apps, schema_editor):
    SessionType = apps.get_model('testsession', 'SessionType')
    for sessiontype in SessionType.objects.all():
        for endpoint in sessiontype.vngendpoint_set.all():
            endpoint.order = 1
            endpoint.save()

class Migration(migrations.Migration):

    dependencies = [
        ('testsession', '0088_auto_20190830_1630'),
    ]

    operations = [
        migrations.RunPython(set_order, remove_order)
    ]

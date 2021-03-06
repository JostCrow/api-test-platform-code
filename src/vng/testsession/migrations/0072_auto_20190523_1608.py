# Generated by Django 2.2.1 on 2019-05-23 14:08

from django.db import migrations, models
import django.db.models.deletion
import uuid


def create_uuid(apps, schema_editor):
    Session = apps.get_model('testsession', 'session')
    for session in Session.objects.all():
        session.cluster = uuid.uuid4()
        session.save()


class Migration(migrations.Migration):

    dependencies = [
        ('testsession', '0071_auto_20190426_1749'),
    ]

    operations = [
        migrations.AddField(
            model_name='session',
            name='cluster',
            field=models.CharField(blank=True, null=True, max_length=50),
        ),
        migrations.RunPython(create_uuid),
        migrations.AlterField(
            model_name='session',
            name='cluster',
            field=models.CharField(editable=False, max_length=50, unique=True),
        ),
        migrations.AddField(
            model_name='sessiontype',
            name='database',
            field=models.BooleanField(default=False, help_text='Check if the a postgres db is needed in the Kubernetes cluster'),
        ),
        migrations.CreateModel(
            name='EnvironmentBoostrap',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('command', models.TextField()),
                ('vng_endpoint', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='testsession.VNGEndpoint')),
            ],
        ),
        migrations.CreateModel(
            name='EnvironmentalVariables',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(max_length=50)),
                ('value', models.CharField(max_length=100)),
                ('vng_endpoint', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='testsession.VNGEndpoint')),
            ],
        ),
    ]

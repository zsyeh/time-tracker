from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('tracker', '0016_session_resources_and_shares'),
    ]

    operations = [
        migrations.AddField(
            model_name='timelog',
            name='encrypted_summary',
            field=models.TextField(blank=True, editable=False),
        ),
        migrations.AddField(
            model_name='timelog',
            name='encrypted_content',
            field=models.TextField(blank=True, editable=False),
        ),
        migrations.AddField(
            model_name='learningissue',
            name='encrypted_content',
            field=models.TextField(blank=True, editable=False),
        ),
        migrations.AddField(
            model_name='githubnotesync',
            name='encrypted_content',
            field=models.TextField(blank=True, editable=False),
        ),
        migrations.CreateModel(
            name='UserDataEncryptionPreference',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('enabled', models.BooleanField(default=False)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='data_encryption_preference', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'user data encryption preference',
                'verbose_name_plural': 'user data encryption preferences',
            },
        ),
    ]

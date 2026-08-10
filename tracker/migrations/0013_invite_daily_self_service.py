from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0012_invite_codes_session_reviews'),
    ]

    operations = [
        migrations.AddField(
            model_name='invitecode',
            name='is_self_service',
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name='invitecode',
            name='issued_local_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name='invitecode',
            constraint=models.CheckConstraint(
                check=(
                    Q(is_self_service=False)
                    | (Q(max_uses=1) & Q(issued_local_date__isnull=False))
                ),
                name='self_service_invite_single_use',
            ),
        ),
        migrations.AddConstraint(
            model_name='invitecode',
            constraint=models.UniqueConstraint(
                condition=Q(is_self_service=True),
                fields=('created_by', 'issued_local_date'),
                name='unique_daily_self_service_invite',
            ),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('drill', '0042_focus_training_blueprints')]
    operations = [
        migrations.AddField(model_name='exampaperitem', name='self_score', field=models.DecimalField(blank=True, null=True, max_digits=5, decimal_places=2)),
        migrations.AddField(model_name='exampaperitem', name='self_note', field=models.TextField(blank=True)),
        migrations.AddConstraint(model_name='exampaperitem', constraint=models.CheckConstraint(
            check=models.Q(self_score__isnull=True) | (models.Q(self_score__gte=0) & models.Q(self_score__lte=models.F('score'))),
            name='drill_paper_item_self_score_range',
        )),
    ]

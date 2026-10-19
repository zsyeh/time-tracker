from django.db import migrations, models
import django.db.models.deletion
import django.core.validators


class Migration(migrations.Migration):
    initial = True
    dependencies = [('drill', '0020_cloud_question_timer')]
    operations = [
        migrations.CreateModel(
            name='SourceQuestionAnchor',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(max_length=96)),
                ('label', models.CharField(max_length=160)),
                ('y', models.FloatField(validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(1)])),
                ('position', models.PositiveIntegerField()),
                ('confidence', models.FloatField(default=1.0)),
                ('asset', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='source_question_anchors', to='drill.questionasset')),
                ('question', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='source_anchor', to='drill.question')),
                ('source_question', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='source_question_anchors', to='drill.question')),
            ],
            options={'ordering': ('source_question_id', 'position')},
        ),
        migrations.AddConstraint(model_name='sourcequestionanchor', constraint=models.UniqueConstraint(fields=('source_question', 'key'), name='drill_source_anchor_key_unique')),
        migrations.AddConstraint(model_name='sourcequestionanchor', constraint=models.UniqueConstraint(fields=('source_question', 'position'), name='drill_source_anchor_pos_unique')),
        migrations.AddConstraint(model_name='sourcequestionanchor', constraint=models.CheckConstraint(check=models.Q(y__gte=0, y__lte=1), name='drill_source_anchor_y_range')),
    ]

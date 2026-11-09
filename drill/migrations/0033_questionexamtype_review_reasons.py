from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('drill', '0032_questionexamtype')]
    operations = [migrations.AddField(
        model_name='questionexamtype', name='review_reasons',
        field=models.JSONField(blank=True, default=list),
    )]

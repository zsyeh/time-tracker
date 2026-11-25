from django.db import migrations, models
class Migration(migrations.Migration):
    dependencies = [('tracker','0022_userpreferences')]
    operations = [migrations.AddField(model_name='timelog',name='pause_intervals',field=models.JSONField(blank=True,default=list))]

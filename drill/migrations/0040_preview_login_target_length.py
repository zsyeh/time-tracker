from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('drill', '0039_search_metadata_coverage_index')]
    operations = [migrations.AlterField(
        model_name='drillloginhandoff', name='target_path',
        field=models.CharField(default='/practice', max_length=16384),
    )]

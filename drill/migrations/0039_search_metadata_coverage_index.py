"""Small metadata-only ID relation for full-catalog coverage aggregation."""
from django.db import migrations


NAME='drill_search_metadata_only'


def install(apps,schema_editor):
    if schema_editor.connection.vendor!='postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute('SELECT i.indisvalid FROM pg_index i JOIN pg_class c ON c.oid=i.indexrelid WHERE c.relname=%s',[NAME])
        row=cursor.fetchone()
        if row and not row[0]:
            cursor.execute('DROP INDEX CONCURRENTLY '+NAME)
        cursor.execute('CREATE INDEX CONCURRENTLY IF NOT EXISTS '+NAME+''' ON drill_questionsearchdocument (question_id)
            WHERE coverage->'has_prompt'='false'::jsonb AND coverage->'has_latex'='false'::jsonb''')


def uninstall(apps,schema_editor):
    if schema_editor.connection.vendor=='postgresql':
        with schema_editor.connection.cursor() as cursor:
            cursor.execute('DROP INDEX CONCURRENTLY IF EXISTS '+NAME)


class Migration(migrations.Migration):
    atomic=False
    dependencies=[('drill','0038_search_postgres_indexes')]
    operations=[migrations.RunPython(install,uninstall,atomic=False)]

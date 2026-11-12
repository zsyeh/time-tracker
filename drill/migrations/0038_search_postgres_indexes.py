"""Optional PostgreSQL access paths; no source data or private text is changed."""
from django.db import migrations

INDEXES = {
    'drill_search_terms_gin': 'CREATE INDEX CONCURRENTLY IF NOT EXISTS drill_search_terms_gin ON drill_questionsearchdocument USING gin (terms jsonb_ops)',
    'drill_lexeme_term_trgm': "CREATE INDEX CONCURRENTLY IF NOT EXISTS drill_lexeme_term_trgm ON drill_questionsearchlexeme USING gin (term gin_trgm_ops) WHERE kind = 'latin'",
    'drill_lexeme_prefix': 'CREATE INDEX CONCURRENTLY IF NOT EXISTS drill_lexeme_prefix ON drill_questionsearchlexeme (workspace,kind,term varchar_pattern_ops)',
}


def install(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm')
        for name, sql in INDEXES.items():
            cursor.execute('SELECT i.indisvalid FROM pg_index i JOIN pg_class c ON c.oid=i.indexrelid WHERE c.relname=%s', [name])
            row = cursor.fetchone()
            if row and not row[0]:
                cursor.execute('DROP INDEX CONCURRENTLY '+name)
            cursor.execute(sql)


def uninstall(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        with schema_editor.connection.cursor() as cursor:
            for name in reversed(INDEXES):
                cursor.execute('DROP INDEX CONCURRENTLY IF EXISTS '+name)
    # pg_trgm may be shared with unrelated apps; never drop the extension.


class Migration(migrations.Migration):
    atomic = False
    dependencies = [('drill','0037_search_dirty_triggers')]
    operations = [migrations.RunPython(install, uninstall, atomic=False)]

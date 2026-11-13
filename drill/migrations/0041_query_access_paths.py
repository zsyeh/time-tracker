"""Small reversible access paths; never rewrite questions or learning rows."""
from django.db import migrations, models


LATEST = models.Index(fields=('user', 'question', '-created_at', '-id'),
                      include=('result',), name='drill_attempt_latest_idx')
DUPLICATE = models.Index(fields=('document', 'question_order'), name='drill_question_order_idx')


def _postgres_create(cursor, index, sql):
    cursor.execute('SELECT i.indisvalid FROM pg_index i JOIN pg_class c '
                   'ON c.oid=i.indexrelid WHERE c.relname=%s', [index])
    row = cursor.fetchone()
    if row and not row[0]:
        cursor.execute('DROP INDEX CONCURRENTLY ' + index)
    cursor.execute(sql)


def _change(apps, schema_editor, reverse=False):
    if schema_editor.connection.vendor != 'postgresql':
        add, remove = (DUPLICATE, LATEST) if reverse else (LATEST, DUPLICATE)
        schema_editor.add_index(apps.get_model('drill', 'Question' if reverse else 'QuestionAttempt'), add)
        schema_editor.remove_index(apps.get_model('drill', 'QuestionAttempt' if reverse else 'Question'), remove)
        return
    with schema_editor.connection.cursor() as cursor:
        # Bound resource use and lock waits on the small production server.
        names = ('lock_timeout', 'statement_timeout', 'maintenance_work_mem')
        old = {}
        for name in names:
            cursor.execute('SHOW ' + name)
            old[name] = cursor.fetchone()[0]
        try:
            for name, value in zip(names, ('3s', '60s', '32MB')):
                cursor.execute('SELECT set_config(%s,%s,false)', [name, value])
            if reverse:
                _postgres_create(cursor, DUPLICATE.name,
                    'CREATE INDEX CONCURRENTLY IF NOT EXISTS drill_question_order_idx '
                    'ON drill_question (document_id, question_order)')
                cursor.execute('DROP INDEX CONCURRENTLY IF EXISTS drill_attempt_latest_idx')
            else:
                # The unique constraint already provides the identical order
                # access path. Refuse to drop the duplicate if it is absent.
                cursor.execute("SELECT indisvalid AND indisunique FROM pg_index "
                               "WHERE indexrelid=to_regclass('drill_question_document_order_unique')")
                if cursor.fetchone() != (True,):
                    raise RuntimeError('Question order unique index must be valid before removing its duplicate.')
                _postgres_create(cursor, LATEST.name,
                    'CREATE INDEX CONCURRENTLY IF NOT EXISTS drill_attempt_latest_idx '
                    'ON drill_questionattempt (user_id, question_id, created_at DESC, id DESC) INCLUDE (result)')
                cursor.execute('DROP INDEX CONCURRENTLY IF EXISTS drill_question_order_idx')
        finally:
            for name, value in old.items():
                cursor.execute('SELECT set_config(%s,%s,false)', [name, value])


def install(apps, schema_editor):
    _change(apps, schema_editor)


def uninstall(apps, schema_editor):
    _change(apps, schema_editor, reverse=True)


class Migration(migrations.Migration):
    atomic = False
    dependencies = [('drill', '0040_preview_login_target_length')]
    operations = [migrations.SeparateDatabaseAndState(
        database_operations=[migrations.RunPython(install, uninstall, atomic=False)],
        state_operations=[
            migrations.AddIndex(model_name='questionattempt', index=LATEST),
            migrations.RemoveIndex(model_name='question', name=DUPLICATE.name),
        ],
    )]

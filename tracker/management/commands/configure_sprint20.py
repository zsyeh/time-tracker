"""Enable the account's sprint plan and idempotently add Timer task presets."""
import datetime
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from tracker.models import StudyTag, TaskPreset
from tracker.user_preferences import patch_preferences, preferences_snapshot


class Command(BaseCommand):
    help = 'Enable 20-day sprint goals for one explicit account; preserve existing tasks and history.'

    def add_arguments(self, parser):
        parser.add_argument('--username', required=True)
        parser.add_argument('--start-date', required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        if options['username'] != 'eh':
            raise CommandError('The sprint plan is available only for account eh.')
        try:
            start = datetime.date.fromisoformat(options['start_date']).isoformat()
            user = get_user_model().objects.select_for_update().get(username=options['username'], is_active=True)
        except (ValueError, get_user_model().DoesNotExist) as exc:
            raise CommandError('Valid date and existing active account required.') from exc
        # Encrypted names must be compared after ORM decryption, never filtered as plaintext SQL.
        tasks = list(TaskPreset.objects.filter(user=user).select_related('parent'))
        tags = list(StudyTag.objects.filter(user=user))
        extra_tag = next((tag for tag in tags if tag.name == '冲刺额外任务'), None)
        if extra_tag is None:
            extra_tag = StudyTag.objects.create(user=user, name='冲刺额外任务', color='gray')
        created = []
        def task(subject, name, parent=None, extra=False):
            row = next((p for p in tasks if p.subject == subject and p.parent_id == (parent.pk if parent else None) and p.name == name), None)
            if row is None:
                row = TaskPreset.objects.create(user=user, subject=subject, name=name, parent=parent, is_home_shortcut=False)
                tasks.append(row)
                created.append(row.pk)
            if row.is_home_shortcut:
                row.is_home_shortcut = False
                row.save(update_fields=['is_home_shortcut', 'updated_at'])
            if extra:
                row.tags.add(extra_tag)
            return row
        task('math', '冲刺 · Selected严选30题 · 300分钟')
        task('major', '冲刺 · 892复测与新考点20–30题 · 240分钟')
        english = task('english', '冲刺 · 英语二基础111分钟')
        for name in ['完形填空 · 15分钟', '阅读一 · 19分钟', '阅读二 · 19分钟', '阅读三 · 19分钟', '阅读四 · 19分钟', '新题型 · 10分钟', '翻译 · 10分钟']:
            task('english', name, parent=english)
        task('training', '冲刺 · 政治30分钟')
        task('english', '冲刺额外 · 英语作文', extra=True)
        for subject, label in [('math', '数学二'), ('major', '892专业课'), ('english', '英语二'), ('training', '政治')]:
            task(subject, f'冲刺额外 · {label}错题订正', extra=True)
        current = preferences_snapshot(user)
        patch_preferences(user, {'schema_version': current['schema_version'], 'changes': {'timer.goal_plan': {'mode': 'sprint20', 'start_date': start}}, 'base_revisions': {'timer.goal_plan': current['field_revisions']['timer.goal_plan']}})
        self.stdout.write(self.style.SUCCESS(f'Sprint enabled: user={user.pk}, start={start}, created_presets={created}. No TimeLog changes.'))

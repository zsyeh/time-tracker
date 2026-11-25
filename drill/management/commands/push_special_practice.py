import json
from pathlib import Path
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from drill.special_practice import push_special_practice

class Command(BaseCommand):
    help='Push an ordered private Practice collection; repeated identical keys are idempotent.'
    def add_arguments(self,parser):
        for field in ('username','workspace','key','title','questions-json'):
            parser.add_argument('--'+field,required=True)
        parser.add_argument('--description',default='')
    def handle(self,*args,**options):
        try:
            user=get_user_model().objects.get(username=options['username'])
            paper,created=push_special_practice(user=user,workspace=options['workspace'],key=options['key'],title=options['title'],description=options['description'],question_uuids=json.loads(Path(options['questions_json']).read_text()))
        except (ValueError,OSError,get_user_model().DoesNotExist) as error:
            raise CommandError(str(error)) from error
        self.stdout.write(json.dumps({'uuid':str(paper.uuid),'created':created,'count':paper.items.count(),'url':f"/{options['workspace']}/special-practice"}))

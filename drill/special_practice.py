"""Agent-delivered ordered collections, reusing immutable paper membership and Practice."""
import uuid
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, OuterRef, Subquery
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import ExamBlueprint, ExamBlueprintSection, ExamPaper, ExamPaperItem, Question, QuestionRevision
from .views import request_workspace

@transaction.atomic
def push_special_practice(*, user, workspace, key, title, question_uuids, description=''):
    if workspace not in ('drill', 'ei'):
        raise ValueError('workspace must be drill or ei')
    if not key or len(key)>120 or not title.strip() or len(title)>160 or len(description)>4000:
        raise ValueError('Invalid key/title/description')
    if not isinstance(question_uuids,list) or not 1<=len(question_uuids)<=1000:
        raise ValueError('Provide 1–1000 ordered question UUIDs')
    ids=[str(uuid.UUID(str(value))) for value in question_uuids]
    if len(set(ids))!=len(ids):
        raise ValueError('Duplicate question UUIDs are not allowed')
    # Serialize idempotent pushes for one owner, including concurrent Agent runs.
    get_user_model().objects.select_for_update().get(pk=user.pk)
    code=f'special-practice-{workspace}-v1'
    existing=ExamPaper.objects.filter(user=user,blueprint__code=code,generation_options__special_practice__key=key).first()
    if existing:
        meta=existing.generation_options['special_practice']
        old=[str(v) for v in existing.items.order_by('position').values_list('question__uuid',flat=True)]
        if old!=ids or meta['title']!=title or meta.get('description','')!=description:
            raise ValueError('This key already exists with different content; use a new key')
        return existing,False
    questions={str(q.uuid):q for q in Question.objects.filter(uuid__in=ids,document__workspace=workspace,is_practiceable=True).select_related('document')}
    if len(questions)!=len(ids):
        raise ValueError('Some question UUIDs are missing, non-practiceable or belong to another workspace')
    blueprint,_=ExamBlueprint.objects.get_or_create(code=code,defaults=dict(title='专练模式',subject='ei' if workspace=='ei' else 'math2',mode='weak',version=30000,duration_minutes=0,total_score=0,cooldown_days=0,is_active=False))
    sections={}
    for q in questions.values():
        if q.question_type not in sections:
            section,_=ExamBlueprintSection.objects.get_or_create(blueprint=blueprint,question_type=q.question_type,defaults=dict(order=[value for value,_ in Question.QUESTION_TYPE_CHOICES].index(q.question_type)+1,title=q.get_question_type_display(),question_count=0,score_per_question=0))
            sections[q.question_type]=section
    paper=ExamPaper.objects.create(user=user,blueprint=blueprint,seed=0,mode='weak',generation_options={'special_practice':dict(key=key,title=title,description=description,source='agent')})
    ExamPaperItem.objects.bulk_create([ExamPaperItem(paper=paper,section=sections[questions[value].question_type],question=questions[value],question_revision=QuestionRevision.capture(questions[value]),position=i+1,score=0,selected_fingerprint=questions[value].fingerprint) for i,value in enumerate(ids)])
    return paper,True

class SpecialPracticeView(APIView):
    def get(self,request):
        first=ExamPaperItem.objects.filter(paper_id=OuterRef('pk')).order_by('position')
        papers=ExamPaper.objects.filter(user=request.user,blueprint__code=f'special-practice-{request_workspace(request)}-v1').annotate(question_count=Count('items'),first_question=Subquery(first.values('question__uuid')[:1]),first_item=Subquery(first.values('pk')[:1])).order_by('-created_at','-pk')[:100]
        return Response({'results':[dict(uuid=str(p.uuid),title=p.generation_options['special_practice']['title'],description=p.generation_options['special_practice'].get('description',''),created_at=p.created_at,question_count=p.question_count,first_question=str(p.first_question) if p.first_question else None,first_item=p.first_item) for p in papers]})

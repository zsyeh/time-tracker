"""Private edits to an existing paper review; source questions remain immutable."""
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import ExamPaper, QuestionUserState
from .views import request_workspace

FIELDS = {'user_answer', 'reference', 'note', 'priority', 'verification'}

class ReviewEditSerializer(serializers.Serializer):
    expected_question_uuid = serializers.UUIDField()
    changes = serializers.DictField(child=serializers.CharField(max_length=10000, allow_blank=True, trim_whitespace=False), allow_empty=False)
    expected = serializers.DictField(child=serializers.CharField(max_length=10000, allow_blank=True, trim_whitespace=False))

    def validate(self, attrs):
        keys = set(attrs['changes'])
        if not keys <= FIELDS or set(attrs['expected']) != keys:
            raise serializers.ValidationError('Only the five review text fields may be edited, with matching expected values.')
        if 'priority' in attrs['changes'] and len(attrs['changes']['priority']) > 64:
            raise serializers.ValidationError('Priority is too long.')
        return attrs

class PaperGradingItemView(APIView):
    @transaction.atomic
    def patch(self, request, paper_uuid, position):
        serializer = ReviewEditSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        paper = get_object_or_404(ExamPaper.objects.select_for_update(), uuid=paper_uuid, user=request.user,
                                 blueprint__subject='ei' if request_workspace(request) == 'ei' else 'math2')
        item = get_object_or_404(paper.items.select_for_update().select_related('question'), position=position)
        if item.question.uuid != data['expected_question_uuid']:
            return Response({'detail':'题目已变化，请刷新后重试。'},status=409)
        grading = paper.generation_options.get('grading')
        row = next((r for r in (grading or {}).get('items',[]) if r['position']==position), None)
        if row is None:
            return Response({'detail':'本题尚无可编辑批阅记录。'},status=400)
        if any(str(row.get(key,'')) != value for key,value in data['expected'].items()):
            return Response({'detail':'批阅内容已在其他页面更新，请刷新核对后再保存。'},status=409)
        changes = {k:v for k,v in data['changes'].items() if v != row.get(k,'')}
        if not changes: return Response({'item':row,'changed':False})
        old = dict(row)
        row.update(changes)
        grading.setdefault('edit_history',[]).append({'position':position,'at':timezone.now().isoformat(),
             'user_id':request.user.pk,'changes':{k:{'before':old.get(k,''),'after':v} for k,v in changes.items()}})
        paper.generation_options = {**paper.generation_options,'grading':grading}
        paper.save(update_fields=['generation_options'])
        fields = []
        if 'user_answer' in changes:
            item.user_answer = row['user_answer'];fields.append('user_answer')
        marker = f'[892批阅 {paper.uuid} {grading["exam_date"]}]'
        if 'note' in changes:
            fragment = marker+'\n'+str(old.get('note',''))
            if fragment in item.self_note:
                item.self_note = item.self_note.replace(fragment,marker+'\n'+row['note'],1)
                fields.append('self_note')
        if fields: item.save(update_fields=fields)
        if {'note','priority'} & changes.keys():
            state = QuestionUserState.objects.select_for_update().filter(user=request.user,question=item.question).first()
            fragment = marker+'\n'+str(old.get('priority',''))+' · '+str(old.get('note',''))
            # Replace only our exact imported paragraph; preserve unrelated/manual notes.
            if state and fragment in state.note:
                state.note = state.note.replace(fragment,marker+'\n'+row['priority']+' · '+row['note'],1)
                state.version += 1
                state.save(update_fields=['note','version','updated_at'])
        return Response({'item':row,'changed':True})

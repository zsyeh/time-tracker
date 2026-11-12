from django.conf import settings
from django.db.models import Q
from rest_framework.response import Response
from rest_framework.views import APIView
from drill.models import QuestionSearchLexeme
from .normalize import aliases, compact, edit_distance, HAN
import re
from .service import get_plan, index_state, read_snapshot, typo_candidates


class QuestionSearchSuggestionsView(APIView):
    def get(self,request):
        from drill.views import request_workspace
        workspace=request_workspace(request)
        plan=get_plan(request.query_params.get('q',''))
        try:
            limit=max(1,min(8,int(request.query_params.get('limit',8))))
        except (ValueError,TypeError):
            return Response({'code':'INVALID_FILTER','detail':'limit must be an integer'},status=400)
        with read_snapshot():
            _,version,hybrid=index_state(workspace,request.query_params)
            results=[]
            if plan.raw and hybrid and getattr(settings,'DRILL_SEARCH_SUGGESTIONS',True):
                lexemes=QuestionSearchLexeme.objects.filter(workspace=workspace,kind__in=('book','topic'),term__startswith=plan.normalized).order_by('-document_frequency','term','target_key')[:limit]
                seen=set()
                for lexeme in lexemes:
                    key=(lexeme.kind,lexeme.target_key)
                    if key in seen:
                        continue
                    seen.add(key)
                    results.append({'kind':'document' if lexeme.kind=='book' else 'topic','label':lexeme.display,'filters':lexeme.target,'reason':'prefix'})
                for row in aliases():
                    chinese_typo = len(plan.normalized)>=3 and re.fullmatch(f'[{HAN}]+', plan.normalized) and any(
                        abs(len(plan.normalized)-len(compact(a)))<=1 and edit_distance(plan.normalized, compact(a))==1
                        for a in row['equivalents'] if re.fullmatch(f'[{HAN}]+', compact(a)))
                    if chinese_typo or plan.normalized in [compact(x) for x in row.get('common_typos',[])]:
                        results.append({'kind':'query','label':row['equivalents'][0],'query':row['equivalents'][0],'reason':'spelling'})
                if len(results)<limit:
                    for word in typo_candidates(workspace,plan.normalized):
                        results.append({'kind':'query','label':word,'query':word,'reason':'spelling'})
            return Response({'query':plan.raw,'index_version':version,'results':results[:limit]})

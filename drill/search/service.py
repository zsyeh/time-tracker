"""Search membership, SQL aggregation, then page-only hydration.

Authentication and workspace/collection scope are supplied by existing views.
No query result is cached across users, and no private note enters the projection.
"""
import datetime
from contextlib import contextmanager
from copy import deepcopy
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import connection, transaction
from django.db.models import Count, Exists, F, OuterRef, Q, Subquery, Value
from django.db.models.expressions import RawSQL
from django.utils import timezone
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.pagination import PageNumberPagination
from drill.models import Question, QuestionAttempt, QuestionMarker, QuestionSearchDirty, QuestionSearchDocument, QuestionSearchState, QuestionUserState
from drill.exam_types import with_exam_type, filter_exam_type, type_group, GROUPS
from .index import aliases_hash, manifest_data, source_version
from .normalize import compact, edit_distance
from .postgres import SearchExpression
from .query import parse_query, SearchQueryError, Variant


class SearchUnavailable(APIException):
    status_code = 503
    default_code = 'SEARCH_INDEX_NOT_READY'


class SearchIndexChanged(APIException):
    status_code = 409
    default_code = 'SEARCH_INDEX_CHANGED'


@contextmanager
def read_snapshot():
    # HTTP views enter here before executing their first scoped search query.
    nested = connection.in_atomic_block
    with transaction.atomic():
        if connection.vendor == 'postgresql':
            with connection.cursor() as cursor:
                if not nested:
                    cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
                elif not any(getattr(block, '_from_testcase', False) for block in connection.atomic_blocks):
                    cursor.execute('SHOW transaction_isolation')
                    if cursor.fetchone()[0] != 'repeatable read':
                        raise ImproperlyConfigured('Search must enter read_snapshot before its first SQL, outside an unrelated atomic block.')
        yield


def get_plan(query):
    try:
        return parse_query(query)
    except SearchQueryError as exc:
        raise ValidationError({'code': exc.code, 'detail': str(exc)})


def index_state(workspace, params):
    if getattr(settings,'DRILL_SEARCH_BACKEND','legacy') != 'hybrid_v1':
        if params.get('index_version') and params['index_version'] != 'legacy:0':
            raise SearchIndexChanged({'code':'SEARCH_INDEX_CHANGED','index_version':'legacy:0'})
        return None, 'legacy:0', False
    state = QuestionSearchState.objects.filter(workspace=workspace).first()
    version = f'{state.schema_version}:{state.aliases_hash[:16]}:{state.generation}' if state else 'legacy:0'
    backend = getattr(settings,'DRILL_SEARCH_BACKEND','legacy')
    hybrid = backend == 'hybrid_v1'
    if hybrid and (not state or not state.ready or state.rebuilding or state.build_source_version != source_version()):
        raise SearchUnavailable({'code':'SEARCH_INDEX_NOT_READY','detail':'Search index is not ready; retry later.'})
    if params.get('index_version') and params['index_version'] != version:
        raise SearchIndexChanged({'code':'SEARCH_INDEX_CHANGED','index_version':version})
    return state, version, hybrid


def legacy_membership(queryset, raw):
    if not raw:
        return queryset
    return queryset.filter(Q(source_label__icontains=raw)|Q(display_label__icontains=raw)|Q(prompt_text__icontains=raw)
        |Q(similarity_topic__title__icontains=raw)|Q(similarity_topic__display_title__icontains=raw))


def hybrid_membership(queryset, plan, workspace, *, ranked=False):
    if not plan.raw:
        return queryset
    if not plan.groups:
        return queryset.none()
    queryset = queryset.filter(document__workspace=workspace)
    if connection.vendor == 'postgresql':
        # A selective public-index relation must be evaluated independently of
        # poorly estimated catalog OR filters. OFFSET 0 prevents flattening, but
        # does NOT force an index: broad single-character queries may seq-scan.
        # No candidate cap; the outer live workspace/collection/user scope remains
        # authoritative. SQL identifiers come only from Django's compiler.
        candidates = QuestionSearchDocument.objects.filter(workspace=workspace,schema_version=1).alias(
            _matched=SearchExpression(plan,prefix='')).filter(_matched=True).order_by().values('question_id')
        sql,params=candidates.query.sql_with_params()
        queryset=queryset.filter(pk__in=RawSQL('SELECT question_id FROM ('+sql+' OFFSET 0) search_candidates',params))
    else:
        queryset = queryset.filter(search_document__workspace=workspace,search_document__schema_version=1).alias(
            _search_matches=SearchExpression(plan)).filter(_search_matches=True)
    if ranked:
        queryset = queryset.annotate(_search_tier=SearchExpression(plan,'tier'),
            _search_score=SearchExpression(plan,'score'), _search_identifier=SearchExpression(plan,'identifier'))
    return queryset


def typo_candidates(workspace, token):
    from drill.models import QuestionSearchLexeme
    from .normalize import aliases
    if not token.isascii() or not token.isalpha() or len(token) < 3:
        return []
    lexemes = QuestionSearchLexeme.objects.filter(workspace=workspace,kind='latin')
    approved = {compact(a) for row in aliases() for a in row['equivalents'] if compact(a).isascii() and compact(a).isalpha()}
    lexemes = lexemes.filter(Q(document_frequency__gte=2)|Q(term__in=approved))
    if connection.vendor == 'postgresql':
        from django.contrib.postgres.search import TrigramSimilarity
        from django.contrib.postgres.lookups import TrigramSimilar
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL pg_trgm.similarity_threshold = 0.25")
        rows = lexemes.filter(TrigramSimilar(F("term"), Value(token))).annotate(sim=TrigramSimilarity('term',token)).order_by('-sim','term').values_list('term','document_frequency')[:32]
    else:
        rows = lexemes.order_by('term').values_list('term','document_frequency')
    # Approved single-word aliases remain usable when the entire workspace is
    # Chinese-only. They are a bounded reviewed vocabulary, not new corpus text.
    vocabulary={word:frequency for word,frequency in rows}
    for word in approved:
        vocabulary.setdefault(word,0)
    candidates=[]
    for word, frequency in vocabulary.items():
        distance=edit_distance(token,word)
        if distance and ((len(token)<=6 and distance<=1) or (len(token)>=7 and distance<=2 and distance/len(token)<=.25)):
            candidates.append((distance,-frequency,word))
    return [row[2] for row in sorted(candidates)[:3]]


def expand_typos(queryset, plan, workspace):
    from .normalize import aliases
    probe=deepcopy(plan)
    probe.groups=[[variant for variant in group if variant.tier<=2] for group in plan.groups]
    if not plan.raw or len(list(hybrid_membership(queryset,probe,workspace).order_by().values_list('pk',flat=True)[:5])) >= 5:
        return plan
    plan=deepcopy(plan)
    for group in plan.groups:
        literal=group[0]
        if len(literal.keys)==1 and literal.keys[0].startswith('en:'):
            for candidate in typo_candidates(workspace,literal.keys[0][3:]):
                group.append(Variant(('en:'+candidate,),4))
                for concept in aliases():
                    if candidate in {compact(alias) for alias in concept['equivalents']}:
                        group.append(Variant(('concept:'+concept['canonical'],),4))
                plan.corrected_terms.append(candidate)
    plan.corrected_terms=list(dict.fromkeys(plan.corrected_terms))
    return plan


def apply_state_filters(queryset, params, user):
    status = params.get('status','all') or 'all'
    if status not in {'all','unattempted','mastered','review','overdue'}:
        raise ValidationError({'code':'INVALID_FILTER','status':'Unknown status.'})
    if params.get('unattempted') == '1':
        if status not in {'all','unattempted'}:
            raise ValidationError({'code':'INVALID_FILTER','status':'Conflicts with unattempted=1.'})
        status='unattempted'
    latest = QuestionAttempt.objects.filter(user=user,question_id=OuterRef('pk')).order_by('-created_at','-pk')
    if status != 'all':
        queryset=queryset.alias(_search_latest=Subquery(latest.values('result')[:1]))
        if status == 'unattempted':
            queryset=queryset.filter(Q(_search_latest__isnull=True)|Q(_search_latest='reset'))
        elif status=='mastered':
            queryset=queryset.filter(_search_latest__in=('done','correct'))
        else:
            queryset=queryset.filter(_search_latest='review')
            if status=='overdue':
                queryset=queryset.alias(_search_last_time=Subquery(latest.values('created_at')[:1])).filter(
                    _search_last_time__lte=timezone.now()-datetime.timedelta(days=5))
    for param,field in [('favorite','is_favorite'),('review_later','review_later')]:
        value=params.get(param,'')
        if value not in {'','0','1','false','true'}:
            raise ValidationError({'code':'INVALID_FILTER',param:'Use 1 or 0.'})
        if value in {'1','true'}:
            queryset=queryset.filter(Exists(QuestionUserState.objects.filter(user=user,question_id=OuterRef('pk'),**{field:True})))
    marker=params.get('marker','').strip()
    if marker in dict(QuestionMarker.MARKER_CHOICES):
        queryset=queryset.filter(Exists(QuestionMarker.objects.filter(user=user,question_id=OuterRef('pk'),code=marker)))
    return queryset


def membership(queryset, request, workspace, *, expand=True):
    state,version,hybrid=index_state(workspace,request.query_params)
    plan=get_plan(request.query_params.get('q',''))
    queryset=apply_state_filters(queryset,request.query_params,request.user)
    if hybrid:
        plan=expand_typos(queryset,plan,workspace) if expand else plan
        queryset=hybrid_membership(queryset,plan,workspace)
    else:
        queryset=legacy_membership(queryset,plan.raw)
    return queryset,plan,state,version,hybrid


def aggregate_types(queryset,user, *, coverage=False):
    latest=QuestionAttempt.objects.filter(user=user,question_id=OuterRef('pk')).order_by('-created_at','-pk')
    extra={'metadata_only':Count('pk',filter=Q(search_document__coverage__has_prompt=False,search_document__coverage__has_latex=False),distinct=True)} if coverage else {}
    rows=list(with_exam_type(queryset).alias(_stats_latest=Subquery(latest.values('result')[:1])).order_by().values('final_question_type').annotate(
        total=Count('pk',distinct=True),attempted=Count('pk',filter=Q(_stats_latest__in=('done','correct','review')),distinct=True),
        mastered=Count('pk',filter=Q(_stats_latest__in=('done','correct')),distinct=True),
        review=Count('pk',filter=Q(_stats_latest='review'),distinct=True),**extra))
    stats={key:{'total':0,'attempted':0,'mastered':0,'review':0} for key in GROUPS}
    for row in rows:
        bucket=stats[type_group(row['final_question_type'])]
        for key in bucket:
            bucket[key]+=row[key]
    return stats,rows


class CountedPage:
    """Pagination adapter: count once from SQL aggregates; slice only thin IDs."""
    def __init__(self,queryset,count):
        self.queryset,self.total=queryset,count
        self.ordered=True
    def count(self):
        return self.total
    def __len__(self):
        return self.total
    def __getitem__(self,key):
        return list(self.queryset[key])


def question_list_response(request):
    from drill.views import workspace_questions, request_workspace, question_progress
    from drill.selected_collections import filter_collection
    from drill.serializers import QuestionSummarySerializer
    workspace=request_workspace(request)
    params=request.query_params
    sort=params.get('sort','relevance' if params.get('q','').strip() else 'source')
    if sort not in {'source','relevance'}:
        raise ValidationError({'code':'INVALID_FILTER','sort':'Use relevance or source.'})
    with read_snapshot():
        queryset=filter_collection(workspace_questions(request),request)
        if params.get('include_structure')!='1':
            queryset=queryset.filter(is_practiceable=True)
        for param,field in [('document','document_id'),('topic','similarity_topic_id')]:
            if params.get(param):
                try:
                    value=int(params[param])
                except (ValueError,TypeError):
                    raise ValidationError({'code':'INVALID_FILTER',param:'Use an integer ID.'})
                queryset=queryset.filter(**{field:value})
        category=params.get('source_category','').strip()
        if category in dict(Question.SOURCE_CATEGORY_CHOICES):
            queryset=queryset.filter(source_category=category)
        if params.get('past_exam')=='1':
            queryset=queryset.filter(source_category='past_exam')
        queryset,plan,state,version,hybrid=membership(queryset,request,workspace)
        stats,type_rows=aggregate_types(queryset,request.user,coverage=hybrid)
        queryset=filter_exam_type(queryset,params)
        count=sum(row['total'] for row in type_rows if (not params.get('exam_type') or row['final_question_type']==params['exam_type'])
            and (not params.get('type_group') or type_group(row['final_question_type'])==params['type_group']))
        if hybrid and plan.raw and sort=='relevance':
            queryset=queryset.annotate(_search_tier=SearchExpression(plan,'tier'),_search_score=SearchExpression(plan,'score'),
                _search_identifier=SearchExpression(plan,'identifier')).order_by('-_search_identifier','_search_tier','-_search_score','document_id','question_order','pk')
        else:
            queryset=queryset.order_by('document_id','question_order','pk')
        paginator=PageNumberPagination();paginator.page_size=24
        page=paginator.paginate_queryset(CountedPage(queryset.values_list('pk',flat=True),count),request)
        ids=list(page)
        # Original summary fields are hydrated only for this page. All Question fields
        # are selected deliberately until a proven safe .only list avoids future N+1.
        hydrated={q.pk:q for q in question_progress(Question.objects.filter(pk__in=ids),request.user).select_related('document','similarity_topic')} if ids else {}
        response=paginator.get_paginated_response(QuestionSummarySerializer([hydrated[pk] for pk in ids],many=True).data)
        if hybrid and plan.groups and ids:
            from .excerpts import search_match
            projections=QuestionSearchDocument.objects.filter(pk__in=ids).only(
                'question_id','terms','labels_norm','book_norm','topics_norm','body_norm','formula_norm','coverage').in_bulk()
            for pk,result in zip(ids,response.data['results']):
                if pk in projections:
                    result['search_match']=search_match(plan,projections[pk])
        response.data['type_statistics']=stats
        if params.get('search_version')=='2' or hybrid:
            metadata_only=0
            if hybrid and count:
                metadata_only=sum(row['metadata_only'] for row in type_rows if (not params.get('exam_type') or row['final_question_type']==params['exam_type'])
                    and (not params.get('type_group') or type_group(row['final_question_type'])==params['type_group']))
            response.data['search']={'version':2,'query':plan.raw,'normalized_query':plan.normalized,'index_version':version,
                'mode':('expanded' if plan.corrected_terms else 'hybrid') if hybrid else 'legacy',
                'reason':'no_terms' if plan.raw and not plan.groups else None,'corrected_terms':plan.corrected_terms,
                'suggestions':[],'stale':bool(state and QuestionSearchDirty.objects.filter(question__document__workspace=workspace).exists()),
                'coverage':{'metadata_only_count':metadata_only}}
        return response

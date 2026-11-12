"""Synthetic search regression fixtures: no real notes, user data or scanned content."""
import datetime
import io
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection
from django.test import TestCase, SimpleTestCase, TransactionTestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient
from .models import (Question,QuestionDocument,QuestionAttempt,QuestionUserState,QuestionSearchDirty,
                     QuestionSearchDocument,QuestionSearchLexeme,QuestionSearchState,QuestionTopic)
from .search.normalize import formula,compact,identifier
from .search.query import parse_query,private_matches,SearchQueryError
from .search.index import process_queue,verify_workspace,index_question,index_batch,enqueue,projection


class SearchNormalizerTests(SimpleTestCase):
    def test_unicode_and_identifiers(self):
        self.assertEqual(compact('Ｆｏｕｒｉｅｒ\u00a0变 换'), 'fourier 变换')
        self.assertEqual(identifier('１－２'),'1-2')
        self.assertNotEqual(identifier('1-2'),identifier('1.2'))
        self.assertEqual(formula('x²'),formula('x^2'))
        self.assertNotEqual(formula('x²'),formula('x2'))
        self.assertEqual(formula('x₁'),formula('x_1'))
        self.assertNotEqual(formula(r'\Pi'),formula(r'\pi'))
    def test_concepts_and_order(self):
        self.assertTrue(private_matches(parse_query('Fourier transform'),'傅里叶变换'))
        self.assertFalse(private_matches(parse_query('Fourier transform'),'傅里叶级数'))
        for q in ('隐函数 偏导数','偏导数 隐函数'):
            self.assertTrue(private_matches(parse_query(q),'隐函数求偏导数'))
        self.assertTrue(private_matches(parse_query('RS触发器'),'RS 触发器'))
        self.assertTrue(private_matches(parse_query('Z 变换'),'Z-transform'))
        self.assertFalse(private_matches(parse_query('Z'),'lazy'))
        self.assertTrue(private_matches(parse_query('拉普拉斯'),'拉氏变换'))
        self.assertTrue(private_matches(parse_query('Laplace transform'),'拉氏变换'))
        self.assertTrue(private_matches(parse_query('Bode'),'波特图'))
        self.assertFalse(private_matches(parse_query('Bode'),'希尔波特变换'))
        self.assertTrue(private_matches(parse_query('RS触发器'),'比较 RS、D、JK、T 触发器'))
        self.assertFalse(private_matches(parse_query('RS触发器'),'doors 与 D 触发器'))
        self.assertFalse(private_matches(parse_query('RS触发器'),'RS','D 触发器'))
        self.assertTrue(private_matches(parse_query('Fourier'),'傅里叶'))
    def test_boundaries_and_formula(self):
        self.assertFalse(private_matches(parse_query('% _ ！'),'ordinary text'))
        with self.assertRaises(SearchQueryError):parse_query('x'*121)
        with self.assertRaises(SearchQueryError):parse_query(' '.join(str(n) for n in range(13)))
        self.assertTrue(private_matches(parse_query(r'\partial'),'∂f'))
        self.assertTrue(private_matches(parse_query(r'\dfrac'),r'\frac{x}{y}'))
        self.assertTrue(private_matches(parse_query('x²'),'设 x^2+1'))
        self.assertFalse(private_matches(parse_query('x²'),'设 x2+1'))
        self.assertTrue(private_matches(parse_query(r'\delta(t-t_0)'),r'定义 $$\delta(t-t_0)$$'))
        self.assertTrue(private_matches(parse_query(r'\frac{1}{1+s/\omega_p}'),r'$$H(s)=\frac{1}{1+s/\omega_p}$$'))
        self.assertTrue(private_matches(parse_query('x^2'),'$x^2+1$'))


SEARCH_SETTINGS=dict(SECURE_SSL_REDIRECT=False,ALLOWED_HOSTS=['drill.test','ei.test'],
                     DRILL_HOSTS={'drill.test'},EI_HOSTS={'ei.test'},DRILL_SEARCH_BACKEND='hybrid_v1')


@override_settings(**SEARCH_SETTINGS)
class SearchAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user=get_user_model().objects.create_user('search-owner')
        cls.other=get_user_model().objects.create_user('search-other')
        cls.doc=QuestionDocument.objects.create(source_id=88001,workspace='drill',filename='M2.pdf',
            title='数学二严选练习册',sha256='search-doc',page_count=1,relation_type='selected_question_book')
        cls.ei=QuestionDocument.objects.create(source_id=88002,workspace='ei',filename='EI.pdf',title='EI signals',sha256='search-ei',page_count=1)
        cls.items=[]
        texts=['多元微分与偏导数 隐函数','傅里叶变换 Fourier transform','傅里叶级数 Fourier series',
               'RS 触发器 逻辑','Z 变换','拉普拉斯变换','卡诺图 Karnaugh map','负反馈 Bode',r'公式 $x^2$ 与 \partial',
               'fourer literal original','Fourier topic header','']
        for n,text in enumerate(texts):
            cls.items.append(Question.objects.create(document=cls.doc,question_order=n,source_label=f'{n+1}-2',
                display_label='Fourier' if n==10 else '',prompt_text=text,fingerprint=f'search-{n}',
                is_practiceable=True,question_type='single_choice' if n%2 else 'solution'))
        for n in range(28):
            cls.items.append(Question.objects.create(document=cls.doc,question_order=20+n,source_label=f'P{n}',
                prompt_text='导数练习',fingerprint=f'page-{n}',is_practiceable=True))
        cls.outside=Question.objects.create(document=cls.ei,question_order=1,prompt_text='导数 Fourier',source_label='other',fingerprint='outside',is_practiceable=True)
        enqueue(Question.objects.values_list('pk',flat=True))
        result=process_queue(200,60)
        assert not result['failed'],result
        assert verify_workspace('drill')['valid']
        assert verify_workspace('ei')['valid']
    def setUp(self):
        self.client=APIClient(HTTP_HOST='drill.test');self.client.force_authenticate(self.user)
    def search(self,q='',**params):
        response=self.client.get('/api/drill/questions/',{'q':q,'search_version':'2',**params})
        self.assertEqual(response.status_code,200,response.data)
        return response.data
    def test_chinese_alias_short_and_formula(self):
        for query,expected in [('多元微分',0),('偏导数',0),('隐函数',0),('Fourier transform',1),('RS触发器',3),
            ('Z-transform',4),('Laplace',5),('K-map',6),('negative feedback',7),('x²',8),(r'\partial',8)]:
            with self.subTest(query=query):
                data=self.search(query)
                self.assertIn(str(self.items[expected].uuid),[r['uuid'] for r in data['results']])
        self.assertEqual(self.search('导')['count'],29)
        self.assertNotIn(str(self.items[2].uuid),[r['uuid'] for r in self.search('Fourier transform')['results']])
    def test_ids_book_scope_and_no_terms(self):
        self.assertEqual(self.search(str(self.items[0].uuid))['results'][0]['uuid'],str(self.items[0].uuid))
        self.assertEqual(self.search(str(self.outside.uuid))['count'],0)
        self.assertEqual(self.search('数学二严选')['count'],len(self.items))
        self.assertEqual(self.search('%_！')['count'],0)
        self.assertEqual(self.search('1-2')['results'][0]['uuid'],str(self.items[0].uuid))

    def test_reviewed_chinese_aliases_match_public_projection(self):
        self.items[5].prompt_text='拉氏变换'
        self.items[5].save()
        self.items[7].prompt_text='波特图'
        self.items[7].save()
        self.items[3].prompt_text='比较 RS、D、JK、T 触发器'
        self.items[3].save()
        self.items[2].prompt_text='希尔波特变换'
        self.items[2].save()
        process_queue(100,20)
        for query,question in [('拉普拉斯',self.items[5]),('Laplace transform',self.items[5]),('Bode',self.items[7]),('RS触发器',self.items[3])]:
            self.assertIn(str(question.uuid),[row['uuid'] for row in self.search(query)['results']])
        self.assertNotIn(str(self.items[2].uuid),[row['uuid'] for row in self.search('Bode')['results']])
    def test_paging_and_version(self):
        first=self.search('导数');second=self.search('导数',page=2,index_version=first['search']['index_version'])
        self.assertEqual(len(first['results']),24)
        self.assertEqual(len(second['results']),5)
        self.assertFalse({r['uuid'] for r in first['results']} & {r['uuid'] for r in second['results']})
        response=self.client.get('/api/drill/questions/',{'q':'导数','page':2,'index_version':'wrong'})
        self.assertEqual(response.status_code,409)
    def test_owner_state_and_done_reset(self):
        QuestionAttempt.objects.create(user=self.user,question=self.items[0],result='done')
        QuestionAttempt.objects.create(user=self.user,question=self.items[1],result='review',created_at=timezone.now()-datetime.timedelta(days=6))
        QuestionAttempt.objects.create(user=self.other,question=self.items[2],result='correct')
        QuestionUserState.objects.create(user=self.other,question=self.items[2],is_favorite=True)
        QuestionUserState.objects.create(user=self.user,question=self.items[0],is_favorite=True)
        self.assertEqual(self.search(status='mastered')['count'],1)
        self.assertEqual(self.search(status='overdue')['count'],1)
        self.assertEqual(self.search(favorite='1')['count'],1)
        stats=self.search()['type_statistics'];self.assertEqual(stats['large']['mastered'],1)
        self.assertEqual(self.search(type_group='small')['type_statistics'],stats)
        QuestionAttempt.objects.create(user=self.user,question=self.items[0],result='reset')
        self.assertEqual(self.search(status='mastered')['count'],0)
        self.assertEqual(self.client.get('/api/drill/questions/',{'status':'review','unattempted':'1'}).status_code,400)
    def test_original_literal_precedes_typo_title(self):
        data=self.search('fourer')
        self.assertEqual(data['results'][0]['uuid'],str(self.items[9].uuid))
        self.assertIn('fourier',data['search']['corrected_terms'])
    def test_english_typo_recalls_reviewed_chinese_only_concept(self):
        for question in self.items:
            if 'fourier' in (question.prompt_text+' '+question.display_label).lower():
                question.prompt_text='傅里叶变换' if question!=self.items[2] else '傅里叶级数'
                question.display_label=''
                question.save()
        process_queue(100,20)
        self.assertFalse(QuestionSearchLexeme.objects.filter(workspace='drill',kind='latin',term='fourier').exists())
        result=self.search('Foureir')
        self.assertGreater(result['count'],0)
        self.assertIn('fourier',result['search']['corrected_terms'])
        self.assertEqual(result['results'][0]['search_match']['kind'],'spelling')
        self.assertEqual(self.search('fourer')['results'][0]['uuid'],str(self.items[9].uuid))
        self.assertEqual(self.search('fo')['search']['corrected_terms'],[])
    def test_real_formula_and_reviewed_chinese_typo_regressions(self):
        self.items[8].prompt_text=r'$$H(s)=\frac{1}{1+s/\omega_p}$$ 与 $$\delta(t-t_0)$$ 以及 $x^2+1$'
        self.items[8].save();process_queue(100,20)
        for raw in (r'\delta(t-t_0)',r'\frac{1}{1+s/\omega_p}','x^2'):
            self.assertIn(str(self.items[8].uuid),[row['uuid'] for row in self.search(raw)['results']])
        self.assertIn(str(self.items[1].uuid),[row['uuid'] for row in self.search('傅里页变换')['results']])
        self.assertIn(str(self.items[0].uuid),[row['uuid'] for row in self.search('偏到数')['results']])
    def test_direct_topic_and_body_rank_above_ancestor_only_match(self):
        parent=QuestionTopic.objects.create(document=self.doc,title='傅里叶变换',source_id=880010,level=1,sort_order=1)
        series=QuestionTopic.objects.create(document=self.doc,parent=parent,title='傅里叶级数',source_id=880011,level=2,sort_order=2)
        transform=QuestionTopic.objects.create(document=self.doc,parent=parent,title='傅里叶变换的位移性质',source_id=880012,level=2,sort_order=3)
        self.items[2].similarity_topic=series;self.items[2].save()
        self.items[1].similarity_topic=transform;self.items[1].save()
        process_queue(100,20)
        for raw in ('傅里叶变换','Fourier transform'):
            ranked=[row['uuid'] for row in self.search(raw)['results']]
            self.assertLess(ranked.index(str(self.items[1].uuid)),ranked.index(str(self.items[2].uuid)))
    def test_zero_does_not_hydrate(self):
        with patch('drill.views.question_progress',side_effect=AssertionError('zero hydrate')):
            self.assertEqual(self.search('zzzznonexistent')['count'],0)
    def test_suggestions_and_disabled_legacy(self):
        data=self.client.get('/api/drill/search/suggestions/',{'q':'数学'}).data
        self.assertEqual(data['results'][0]['kind'],'document')
        self.assertEqual(data['results'][0]['filters']['document'],self.doc.pk)
        self.assertEqual(self.client.get('/api/drill/search/suggestions/',{'q':''}).data['results'],[])
        with override_settings(DRILL_SEARCH_BACKEND='legacy'):
            self.assertEqual(self.search('导数')['search']['mode'],'legacy')
    def test_dirty_retry_and_lexeme_idempotence(self):
        before=list(QuestionSearchLexeme.objects.order_by('pk').values_list('term','document_frequency'))
        index_question(self.items[1].pk)
        self.assertEqual(before,list(QuestionSearchLexeme.objects.order_by('pk').values_list('term','document_frequency')))
        enqueue([self.items[1].pk])
        with patch('drill.search.index.projection',side_effect=ValueError('SEARCH_SOURCE_TOO_LONG')):
            result=process_queue(100,20)
        self.assertEqual(result['failed'],1)
        dirty=QuestionSearchDirty.objects.get(pk=self.items[1].pk)
        self.assertEqual(dirty.attempts,1)
        self.assertEqual(dirty.last_error_code,'SEARCH_SOURCE_TOO_LONG')
        enqueue([self.items[1].pk]);dirty.refresh_from_db();self.assertEqual(dirty.attempts,0)
    def test_rebuild_dry_run_and_verify(self):
        state=QuestionSearchState.objects.get(workspace='drill')
        call_command('rebuild_question_search',workspace='drill',dry_run=True,stdout=io.StringIO())
        state.refresh_from_db();self.assertTrue(state.ready)
        self.assertTrue(verify_workspace('drill')['valid'])
    def test_batch_rebuild_idempotence_and_refs(self):
        ids=[question.pk for question in self.items]
        before=list(QuestionSearchLexeme.objects.order_by('workspace','kind','term','target_key').values_list(
            'workspace','kind','term','target_key','document_frequency'))
        self.assertEqual(index_batch(ids),len(ids))
        self.assertEqual(index_batch(ids),len(ids))
        self.assertEqual(before,list(QuestionSearchLexeme.objects.order_by('workspace','kind','term','target_key').values_list(
            'workspace','kind','term','target_key','document_frequency')))
        self.assertTrue(verify_workspace('drill')['valid'])
    def test_verify_does_not_publish_when_rebuild_starts(self):
        from django.db.models.query import QuerySet
        original=QuerySet.update
        def racing_rebuild(queryset,**values):
            if queryset.model is QuestionSearchState and values.get('ready') is True:
                original(QuestionSearchState.objects.filter(workspace='drill'),ready=False,rebuilding=True)
            return original(queryset,**values)
        with patch.object(QuerySet,'update',racing_rebuild):
            self.assertFalse(verify_workspace('drill')['valid'])
        state=QuestionSearchState.objects.get(workspace='drill')
        self.assertFalse(state.ready);self.assertTrue(state.rebuilding)

    def test_public_excerpts_codepoints_alias_and_metadata(self):
        question=self.items[0]
        question.prompt_text='😀'*12+'偏导数'+'学习'*100
        question.answer_markdown='PRIVATE_ANSWER_SENTINEL'
        question.save()
        process_queue(100,20)
        match=self.search('partial derivative')['results'][0]['search_match']
        self.assertEqual(match['kind'],'alias')
        self.assertEqual(match['coverage'],'text')
        self.assertIn('body',match['fields'])
        self.assertLessEqual(len(match['excerpt']),160)
        self.assertIn('偏导数',[match['excerpt'][left:right] for left,right in match['highlights']])
        self.assertNotIn('PRIVATE_ANSWER_SENTINEL',str(match))
        result=self.search('数学二严选')['results']
        metadata=next(row for row in result if row['uuid']==str(self.items[11].uuid))
        self.assertEqual(metadata['search_match']['coverage'],'metadata')
        self.assertEqual(metadata['search_match']['fields'],['book'])
        with override_settings(DRILL_SEARCH_BACKEND='legacy'):
            self.assertNotIn('search_match',self.search('偏导数')['results'][0])


@override_settings(**SEARCH_SETTINGS)
class SearchPostgresSyncTests(TransactionTestCase):
    """Real PostgreSQL triggers, including queryset.update/bulk inserts and deletes."""
    def setUp(self):
        if connection.vendor != 'postgresql':
            self.skipTest('PostgreSQL trigger semantics')
        for workspace in ('drill','ei'):
            QuestionSearchState.objects.get_or_create(workspace=workspace)
        self.doc=QuestionDocument.objects.create(source_id=99101,workspace='drill',filename='fixture',title='Fixture',sha256='trigger-doc',page_count=1)
        self.other=QuestionDocument.objects.create(source_id=99102,workspace='ei',filename='fixture2',title='Other',sha256='trigger-doc2',page_count=1)
        self.q=Question.objects.create(document=self.doc,question_order=1,source_label='1-1',prompt_text='Fourier transform',fingerprint='trigger-q',is_practiceable=True)
        process_queue(100,20);verify_workspace('drill');verify_workspace('ei')
    def generation(self,workspace='drill'):
        return QuestionSearchState.objects.get(workspace=workspace).generation
    def test_bulk_update_immediate_version_and_worker(self):
        old=self.generation()
        Question.objects.filter(pk=self.q.pk).update(question_order=99,prompt_text='Laplace transform')
        self.assertGreater(self.generation(),old)
        self.assertTrue(QuestionSearchDirty.objects.filter(pk=self.q.pk).exists())
        self.assertIn('en:fourier',QuestionSearchDocument.objects.get(pk=self.q.pk).terms)
        process_queue(100,20)
        self.assertIn('en:laplace',QuestionSearchDocument.objects.get(pk=self.q.pk).terms)
        self.assertFalse(QuestionSearchLexeme.objects.filter(workspace='drill',term='fourier').exists())
        self.assertTrue(verify_workspace('drill')['valid'])
    def test_workspace_move_and_delete_frequency(self):
        old,new=self.generation(),self.generation('ei')
        Question.objects.filter(pk=self.q.pk).update(document=self.other)
        self.assertGreater(self.generation(),old);self.assertGreater(self.generation('ei'),new)
        process_queue(100,20)
        self.assertEqual(QuestionSearchDocument.objects.get(pk=self.q.pk).workspace,'ei')
        self.assertFalse(QuestionSearchLexeme.objects.filter(workspace='drill',term='fourier').exists())
        self.q.delete()
        self.assertFalse(QuestionSearchDocument.objects.exists())
        self.assertFalse(QuestionSearchLexeme.objects.exists())
    def test_new_revision_survives_worker_old_snapshot(self):
        enqueue([self.q.pk]);revision=QuestionSearchDirty.objects.get(pk=self.q.pk).revision
        original=projection
        def concurrent_change(question):
            values=original(question)
            Question.objects.filter(pk=question.pk).update(prompt_text='new revised text')
            return values
        with patch('drill.search.index.projection',side_effect=concurrent_change):
            index_question(self.q.pk,revision)
        self.assertGreater(QuestionSearchDirty.objects.get(pk=self.q.pk).revision,revision)
        process_queue(100,20)
        self.assertTrue(verify_workspace('drill')['valid'])
    def test_batch_revision_survives_and_failure_rolls_back(self):
        enqueue([self.q.pk]);revision=QuestionSearchDirty.objects.get(pk=self.q.pk).revision
        original=projection
        def concurrent_change(question):
            values=original(question)
            Question.objects.filter(pk=question.pk).update(prompt_text='batch new revised text')
            return values
        with patch('drill.search.index.projection',side_effect=concurrent_change):
            index_batch([self.q.pk])
        self.assertGreater(QuestionSearchDirty.objects.get(pk=self.q.pk).revision,revision)
        index_batch([self.q.pk])
        self.assertTrue(verify_workspace('drill')['valid'])
        before=QuestionSearchDocument.objects.get(pk=self.q.pk).source_hash
        frequencies=list(QuestionSearchLexeme.objects.order_by('pk').values_list('term','document_frequency'))
        Question.objects.filter(pk=self.q.pk).update(prompt_text='rollbacknewlexeme')
        with patch('drill.search.index.QuestionSearchDocument.objects.bulk_create',side_effect=ValueError('fixture failure')):
            with self.assertRaises(ValueError):index_batch([self.q.pk])
        self.assertEqual(QuestionSearchDocument.objects.get(pk=self.q.pk).source_hash,before)
        self.assertEqual(frequencies,list(QuestionSearchLexeme.objects.order_by('pk').values_list('term','document_frequency')))
        index_batch([self.q.pk])
        self.assertTrue(verify_workspace('drill')['valid'])
    def test_private_learning_does_not_dirty_shared_index(self):
        user=get_user_model().objects.create_user('private-owner')
        old=self.generation()
        QuestionAttempt.objects.create(user=user,question=self.q,result='review',note='private sentinel')
        QuestionUserState.objects.create(user=user,question=self.q,note='another private sentinel')
        self.assertEqual(self.generation(),old)
        self.assertFalse(QuestionSearchDirty.objects.exists())
        terms=QuestionSearchDocument.objects.get(pk=self.q.pk).terms
        self.assertNotIn('en:private',terms)
    def test_membership_only_answer_and_errata_invalidate(self):
        from .models import QuestionErratum
        old=self.generation()
        Question.objects.filter(pk=self.q.pk).update(answer_markdown='secret answer text')
        self.assertGreater(self.generation(),old)
        self.assertFalse(QuestionSearchDirty.objects.exists())
        self.assertNotIn('en:secret',QuestionSearchDocument.objects.get(pk=self.q.pk).terms)
        user=get_user_model().objects.create_user('erratum-owner')
        old=self.generation()
        QuestionErratum.objects.create(question=self.q,reporter=user,kind='other',description='private report')
        self.assertGreater(self.generation(),old)
    def test_old_collector_raw_question_delete_cleans_derived_foreign_keys(self):
        enqueue([self.q.pk])
        with connection.cursor() as cursor:
            cursor.execute('DELETE FROM drill_question WHERE id=%s',[self.q.pk])
        self.assertFalse(QuestionSearchDocument.objects.filter(pk=self.q.pk).exists())
        self.assertFalse(QuestionSearchDirty.objects.filter(pk=self.q.pk).exists())
        self.assertFalse(QuestionSearchLexeme.objects.exists())
    def test_two_connections_deleting_shared_lexemes_leave_no_zero_rows(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections
        self.q.delete()
        for attempt in range(4):
            questions=[Question.objects.create(document=self.doc,question_order=n,
                prompt_text='Shared Fourier transform',fingerprint=f'parallel-{attempt}-{n}',is_practiceable=True) for n in (1,2)]
            index_batch([question.pk for question in questions])
            barrier=Barrier(2)
            def delete_source(pk):
                close_old_connections()
                try:
                    barrier.wait(timeout=5)
                    with connection.cursor() as cursor:
                        cursor.execute('DELETE FROM drill_question WHERE id=%s',[pk])
                finally:
                    connection.close()
            with ThreadPoolExecutor(max_workers=2) as pool:
                list(pool.map(delete_source,[question.pk for question in questions]))
            self.assertFalse(QuestionSearchLexeme.objects.exists())
            self.assertTrue(verify_workspace('drill')['valid'])
    def test_indexes_and_read_transaction(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT c.relname,i.indisvalid FROM pg_class c JOIN pg_index i ON i.indexrelid=c.oid WHERE c.relname IN ('drill_search_terms_gin','drill_lexeme_term_trgm','drill_lexeme_prefix')")
            rows=cursor.fetchall()
        self.assertEqual(len(rows),3);self.assertTrue(all(valid for _,valid in rows))
        from .search.service import read_snapshot
        with read_snapshot():
            with connection.cursor() as cursor:
                cursor.execute('SHOW transaction_isolation');self.assertEqual(cursor.fetchone()[0],'repeatable read')
                cursor.execute('SHOW transaction_read_only');self.assertEqual(cursor.fetchone()[0],'on')


@override_settings(SECURE_SSL_REDIRECT=False,ALLOWED_HOSTS=['testserver'])
class PrivateSearchOracleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from tracker.models import TimeLog
        cls.user=get_user_model().objects.create_user('private-search-oracle')
        cls.other=get_user_model().objects.create_user('private-search-outsider')
        cls.texts=['傅里叶变换','Fourier transform','Ｆｏｕｒｉｅｒ transform','&#70;ourier transform',
            'F**ourier** transform',r'\partial f','导数 偏导数','ℱourier transform','Fourer typo literal',
            'Straße','RS 触发器','卡诺图','Z-transform','x²','比较 RS、D、JK、T 触发器','inert plain record']
        for user in (cls.user,cls.other):
            TimeLog.objects.bulk_create([TimeLog(user=user,category='math',status='completed',title='Synthetic record',
                details=cls.texts[n] if n<len(cls.texts) else 'ordinary unrelated text',
                start_time=timezone.now()-datetime.timedelta(minutes=n+1),end_time=timezone.now()-datetime.timedelta(minutes=n)) for n in range(10000)],batch_size=500)
    def test_concepts_across_body_and_separate_tags(self):
        from tracker.models import TimeLog, StudyTag
        from tracker.api_views import _private_session_candidates
        session=TimeLog.objects.filter(user=self.user).first()
        session.title='导数';session.details='plain';session.save()
        core=StudyTag.objects.create(user=self.user,name='核心')
        one=StudyTag.objects.create(user=self.user,name='独立')
        two=StudyTag.objects.create(user=self.user,name='联合')
        session.tags.add(core,one,two)
        for raw in ('导数 核心','独立 联合'):
            plan=parse_query(raw)
            self.assertTrue(private_matches(plan,session.title,*(tag.name for tag in session.tags.all())))
            candidates=_private_session_candidates(TimeLog.objects.filter(user=self.user),plan,self.user)
            self.assertTrue(candidates.filter(pk=session.pk).exists())

    def test_prefilter_equals_full_owner_scan_in_10000_plus_10000(self):
        from tracker.models import TimeLog
        from tracker.api_views import _private_session_candidates
        records=list(TimeLog.objects.filter(user=self.user).values_list('pk','title','details'))
        for raw in ('Fourier transform','Fourier','Fourer','导','偏导数','RS触发器','K-map','Z 变换',r'\partial','x^2','strasse','%_'):
            plan=parse_query(raw)
            expected={pk for pk,title,details in records if private_matches(plan,title,details,_prefilter=False)}
            candidates=_private_session_candidates(TimeLog.objects.filter(user=self.user),plan,self.user)
            actual={row.pk for row in candidates if private_matches(plan,row.title,row.details)}
            with self.subTest(query=raw):
                self.assertEqual(actual,expected)
                self.assertFalse(candidates.exclude(user=self.user).exists())
        self.assertTrue(private_matches(parse_query('Fourier transform'),'傅里叶变换'))
        self.assertTrue(private_matches(parse_query('strasse'),'Straße'))

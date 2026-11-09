import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from .models import Question,QuestionAsset,QuestionDocument,QuestionTopic,QuestionAttempt,QuestionUserState
from .selected_topic_classification import build_export,import_results,rollback_import,placeholder


class SelectedTopicDataTests(TestCase):
    def setUp(self):
        self.manifests=patch('drill.selected_topic_classification.COURSES',[])
        self.manifests.start();self.addCleanup(self.manifests.stop)
        self.doc=QuestionDocument.objects.create(source_id=88121,workspace='drill',title='积分',display_title='积分',sha256='f'*64,page_count=1)
        self.generic=QuestionTopic.objects.create(source_id=88122,document=self.doc,title='严选题',level=1,sort_order=1)
        self.knowledge=QuestionTopic.objects.create(source_id=88123,document=self.doc,title='换元积分',level=2,sort_order=2)
        self.q=Question.objects.create(document=self.doc,question_order=1,topic=self.generic,similarity_topic=self.generic,
            source_label='Original selected Q',prompt_text='Calculate the integral',fingerprint='e'*64,
            answer_source='daguan_answer_guide_pdf',topic_classification_source='import',topic_classification_confidence=.5)
        self.good=Question.objects.create(document=self.doc,question_order=2,topic=self.knowledge,similarity_topic=self.knowledge,
            prompt_text='Known topic',fingerprint='d'*64,answer_source='daguan_answer_guide_pdf')
        self.outside=Question.objects.create(document=self.doc,question_order=3,topic=self.generic,similarity_topic=self.generic,
            prompt_text='Not selected',fingerprint='c'*64)
        self.asset=QuestionAsset.objects.create(source_id=88124,question=self.q,position=0,asset_type='question_crop',
            image_data=b'original image',sha256=hashlib.sha256(b'original image').hexdigest(),width=10,height=10)
        self.user=get_user_model().objects.create_user('topic-owner')
        QuestionAttempt.objects.create(user=self.user,question=self.q,result='review')
        QuestionUserState.objects.create(user=self.user,question=self.q,note='Private note must not enter API export')
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.results=Path(self.temp.name)/'results.jsonl';self.backup=Path(self.temp.name)/'backup.json'
        self.export=build_export()
        self.write_result()

    def write_result(self,**patches):
        row=self.export['questions'][0]
        result={'question_id':row['question_id'],'uuid':row['uuid'],'workspace':row['workspace'],'content_hash':row['content_hash'],
            'topic_id':self.knowledge.pk,'classification_version':'selected-knowledge-v1',
            'model_id':'gpt-6.1-terra','reason':'积分换元','approximate':False,**patches}
        self.results.write_text(json.dumps(result)+'\n')

    def test_export_only_placeholders_and_uses_existing_topics_without_private_notes_or_blobs(self):
        with CaptureQueriesContext(connection) as queries: data=build_export()
        self.assertEqual([q['question_id'] for q in data['questions']],[self.q.pk])
        self.assertEqual(data['summary']['preserved_meaningful'],{'drill':1})
        self.assertNotIn('Private note',json.dumps(data))
        self.assertFalse(any('"image_data"' in q['sql'] for q in queries))
        allowed=[t['topic_id'] for pool in data['pools'].values() for t in pool]
        self.assertEqual(allowed,[self.knowledge.pk])

    def test_dry_run_apply_idempotence_and_exact_rollback_preserve_bank_and_learning(self):
        self.assertEqual(import_results(self.export,self.results)['updated'],0)
        self.q.refresh_from_db();self.assertEqual(self.q.similarity_topic_id,self.generic.pk)
        before_topics=QuestionTopic.objects.count()
        result=import_results(self.export,self.results,apply=True,backup_path=self.backup,batch_id='unit01')
        self.assertEqual(result['updated'],1)
        self.q.refresh_from_db()
        self.assertEqual(self.q.similarity_topic_id,self.knowledge.pk)
        self.assertEqual(self.q.topic_id,self.generic.pk)
        self.assertEqual(self.q.document_id,self.doc.pk)
        self.assertEqual(self.q.fingerprint,'e'*64)
        self.assertEqual(self.q.source_label,'Original selected Q')
        self.assertEqual(self.q.question_type,'unknown')
        self.assertEqual(QuestionTopic.objects.count(),before_topics)
        self.assertEqual(QuestionAttempt.objects.count(),1)
        self.assertEqual(QuestionUserState.objects.get().note,'Private note must not enter API export')
        self.asset.refresh_from_db();self.assertEqual(bytes(self.asset.image_data),b'original image')
        self.assertEqual(import_results(self.export,self.results,apply=True,backup_path=self.backup,batch_id='unit01')['updated'],0)
        self.assertEqual(rollback_import(self.backup)['restored'],1)
        self.q.refresh_from_db();self.assertEqual(self.q.similarity_topic_id,self.generic.pk)
        self.assertEqual(self.q.topic_classification_source,'import')
        self.assertEqual(self.q.topic_classification_confidence,.5)

    def test_stale_metadata_or_new_human_classification_prevent_writes(self):
        self.q.similarity_topic=self.knowledge;self.q.save(update_fields=['similarity_topic'])
        with self.assertRaisesMessage(ValueError,'classification changed'):
            import_results(self.export,self.results,apply=True,backup_path=self.backup,batch_id='unit01')
        self.q.similarity_topic=self.generic;self.q.source_label='Revised source';self.q.save()
        with self.assertRaisesMessage(ValueError,'changed; refresh export'):
            import_results(self.export,self.results,apply=True,backup_path=self.backup,batch_id='unit01')
        self.assertFalse(self.backup.exists())

    def test_wrong_topic_stale_hash_duplicate_and_incomplete_output_are_rejected(self):
        for overrides in ({'topic_id':self.generic.pk},{'content_hash':'x'*64},{'topic_id':None}):
            self.write_result(**overrides)
            with self.assertRaises(ValueError): import_results(self.export,self.results)
        self.write_result();self.results.write_text(self.results.read_text()*2)
        with self.assertRaisesMessage(ValueError,'duplicate'): import_results(self.export,self.results)
        self.results.write_text('')
        with self.assertRaisesMessage(ValueError,'incomplete'): import_results(self.export,self.results)

    def test_rollback_refuses_later_edits(self):
        import_results(self.export,self.results,apply=True,backup_path=self.backup,batch_id='unit01')
        Question.objects.filter(pk=self.q.pk).update(topic_classification_source='human')
        with self.assertRaisesMessage(ValueError,'Later edits'): rollback_import(self.backup)

    def test_generic_year_and_format_labels_are_placeholders_but_knowledge_is_preserved(self):
        for title in ('严选题','2003年真题 · 版本2','课后题 · 第 3 章','背诵简答',''):
            self.assertTrue(placeholder(title))
        for title in ('一阶 RC / RL 电路三要素法','傅里叶变换及其应用','计算二重积分'):
            self.assertFalse(placeholder(title))

    def test_mixed_electronics_book_can_use_both_existing_subject_catalogs_without_moving_question(self):
        from types import SimpleNamespace
        analog=QuestionDocument.objects.create(source_id=88200,workspace='ei',title='892 · 模拟电子技术',sha256='a'*64,page_count=1)
        digital=QuestionDocument.objects.create(source_id=88201,workspace='ei',title='892 · 数字电子技术',sha256='b'*64,page_count=1)
        a=QuestionTopic.objects.create(source_id=88202,document=analog,title='功率放大电路',level=2,sort_order=1)
        d=QuestionTopic.objects.create(source_id=88203,document=digital,title='触发器',level=2,sort_order=1)
        past=QuestionDocument.objects.create(source_id=88204,workspace='ei',title='电子线路（数电·模电）',sha256='1'*64,page_count=1)
        year=QuestionTopic.objects.create(source_id=88205,document=past,title='2020年真题',level=1,sort_order=1)
        question=Question.objects.create(document=past,question_order=1,topic=year,similarity_topic=year,fingerprint='2'*64)
        module=SimpleNamespace(manifest=lambda:{'questions':[{'uuid':str(question.uuid),'fingerprint':question.fingerprint}]})
        with patch('drill.selected_topic_classification.COURSES',[('digital','数电',module)]):
            data=build_export()
        row=next(q for q in data['questions'] if q['question_id']==question.pk)
        self.assertEqual(row['courses'],['digital'])
        self.assertEqual({topic['topic_id'] for topic in data['pools'][row['pool']]},{a.pk,d.pk})
        question.refresh_from_db()
        self.assertEqual(question.document_id,past.pk)
        self.assertEqual(question.topic_id,year.pk)
        self.assertEqual(question.similarity_topic_id,year.pk)

from argparse import Namespace
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from scripts.classify_selected_topics import classify_batch,validate,reuse_expanded_catalog,TERRA,SOL

class SelectedTopicAPITests(TestCase):
    def setUp(self):
        self.row={'question_id':1,'uuid':'u','workspace':'drill','prompt_text':'A readable mathematical question '*3,
                  'latex_text':'','assets':[],'content_hash':'a'*64}
        self.pool=[{'topic_id':11,'path':'积分'}]
        self.args=Namespace()
    def result(self,topic=11):
        return {1:{'question_id':1,'topic_id':topic,'reason':'积分','approximate':False}}
    def test_terra_is_default_and_sol_is_only_used_for_unresolved(self):
        with patch('scripts.classify_selected_topics.request',return_value=self.result()) as request:
            rows=classify_batch([self.row],self.pool,self.args)
            self.assertEqual(rows[0]['model_id'],TERRA)
            self.assertEqual(request.call_count,1)
        with patch('scripts.classify_selected_topics.request',side_effect=[self.result(None),self.result()]) as request:
            rows=classify_batch([self.row],self.pool,self.args)
            self.assertEqual(rows[0]['model_id'],SOL)
            self.assertEqual([call.args[2] for call in request.call_args_list],[TERRA,SOL])
    def test_api_failure_falls_back_and_does_not_invent_a_label(self):
        with patch('scripts.classify_selected_topics.request',side_effect=RuntimeError('offline')):
            rows=classify_batch([self.row],self.pool,self.args)
            self.assertIsNone(rows[0]['topic_id'])
    def test_validation_rejects_cross_pool_duplicate_and_missing_ids(self):
        for items in ([{'question_id':1,'topic_id':12,'reason':'bad','approximate':False}],[],
                      [{'question_id':1,'topic_id':11,'reason':'a','approximate':False}]*2):
            with self.assertRaises(ValueError): validate(items,[self.row],self.pool)

    def test_catalog_expansion_can_reuse_valid_answers_but_not_changed_questions(self):
        before={**self.row,'pool':'old'}
        after={**self.row,'pool':'new','content_hash':'b'*64}
        old={'questions':[before],'pools':{'old':[{'topic_id':11,'path':'积分'}]}}
        new={'pools':{'new':[{'topic_id':11,'path':'积分'},{'topic_id':12,'path':'微分'}]}}
        answer={**self.result()[1],'content_hash':before['content_hash']}
        reused=reuse_expanded_catalog(answer,after,new,old)
        self.assertEqual(reused['content_hash'],'b'*64)
        self.assertEqual(reused['cache_reused_from_hash'],'a'*64)
        self.assertIsNone(reuse_expanded_catalog(answer,{**after,'prompt_text':'changed'},new,old))
        self.assertIsNone(reuse_expanded_catalog({**answer,'topic_id':None},after,new,old))
        self.assertIsNone(reuse_expanded_catalog(answer,after,{'pools':{'new':[]}},old))

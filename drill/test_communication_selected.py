from unittest.mock import patch
from django.test import SimpleTestCase

from .communication_selected import manifest,review_manifest
from .communication_selected_views import CommunicationSelectedView
from .communication_selection_rules import classify
from .test_circuit_selected import CircuitCollectionTests as CollectionFixture
from .views import DrillQuestionDetailView
from .web_views import _safe_drill_target


class CommunicationRulesTests(SimpleTestCase):
    def test_partition_and_honest_matched_filter_coverage(self):
        m=manifest();r=review_manifest()['records']
        ids=[q['uuid'] for q in m['questions']]+[q['uuid'] for q in r]
        self.assertEqual(len(ids),178);self.assertEqual(len(set(ids)),178)
        self.assertEqual({q['bucket'] for q in m['questions']},{b['key'] for b in m['buckets']})
        matched=[q for q in m['questions'] if q['bucket']=='matched_filter']
        self.assertEqual(len(matched),3);self.assertTrue(all(q['kind']=='concept' for q in matched))
        self.assertTrue(m['coverage_notes'])
        repaired=[q for q in m['questions'] if q['label'] in ['课后题 5-22','课后题 5-23','课后题 5-24']]
        self.assertEqual(len(repaired),3);self.assertTrue(all(q['bucket']=='isi' for q in repaired))
        self.assertEqual(_safe_drill_target('/communication-selected?material=ready',site='ei'),'/communication-selected?material=ready')

    def test_five_priority_templates(self):
        self.assertEqual(classify('升余弦滚降特性，求滚降系数、无码间串扰码元速率')['bucket'],'isi')
        self.assertEqual(classify('矩形信号匹配滤波器，求冲激响应、能量、最大输出信噪比')['bucket'],'matched_filter')
        self.assertEqual(classify('PCM量化256级，求信息速率，用香农容量判断')['bucket'],'pcm_capacity')
        self.assertEqual(classify('DSB-SC和SSB调制，画双边频谱求带宽')['bucket'],'analog_mod')
        self.assertEqual(classify('2ASK、2FSK、2PSK求第一零点带宽')['bucket'],'binary_mod')

    def test_scope_and_common_false_positives(self):
        self.assertEqual(classify('接收匹配滤波器的抽样输出为±1V，试求误码率')['bucket'],'receiver_basics')
        self.assertEqual(classify('无码间串扰条件在最佳抽样时刻满足什么形式')['bucket'],'isi')
        self.assertEqual(classify('与s(t)匹配的滤波器冲激响应一般写成什么形式')['bucket'],'matched_filter')
        self.assertEqual(classify('证明升余弦单位冲激响应完整公式')['status'],'review')
        self.assertEqual(classify('试证明其单位冲激响应为下式')['status'],'review')
        self.assertEqual(classify('迫零法设计3抽头均衡器')['status'],'review')
        self.assertEqual(classify('用上题调制信号计算调频带宽')['status'],'review')
        self.assertEqual(classify('试证明16QAM最大功率平均功率比')['status'],'review')
        self.assertEqual(classify('',topic='匹配滤波接收')['status'],'review')


class CommunicationCollectionTests(CollectionFixture):
    def setUp(self):
        super().setUp()
        m={'title':'通信严选','basis':'Study priorities','inventory_count':4,'questions':self.rows,
           'coverage_notes':['Matched-filter calculation gap'],
           'buckets':[dict(key=k,title=k,rank=i,tier='core',focus='Practice') for i,k in enumerate(['first_order','thevenin'],1)]}
        for target,value in [('drill.communication_selected.manifest',m),('drill.communication_selected_views.manifest',m),
                             ('drill.communication_selected_views.review_manifest',{'records':[]})]:
            p=patch(target,return_value=value);p.start();self.addCleanup(p.stop)

    def get(self,query='',*,view=CommunicationSelectedView,question=None,user=None,host='ei.test'):
        return super().get(query.replace('collection=circuit_selected','collection=communication_selected'),view=view,question=question,user=user,host=host)

    def test_notes_and_navigation_are_collection_scoped(self):
        self.assertEqual(self.get().data['coverage_notes'],['Matched-filter calculation gap'])
        with patch('drill.digital_selected.manifest',return_value={'questions':[],'buckets':[]}):
            result=self.get('collection=communication_selected&bucket=first_order',view=DrillQuestionDetailView,question=self.q1)
            self.assertEqual(result.data['next_question_uuid'],str(self.q2.uuid))

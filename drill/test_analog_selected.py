from unittest.mock import patch
from django.test import SimpleTestCase

from .analog_selected import manifest, review_manifest
from .analog_selected_views import AnalogSelectedView
from .analog_selection_rules import classify
from .test_circuit_selected import CircuitCollectionTests as CollectionFixture
from .views import DrillQuestionDetailView
from .web_views import _safe_drill_target


class AnalogRulesTests(SimpleTestCase):
    def test_partition_and_original_identity(self):
        m,review=manifest(),review_manifest()['records']
        ids=[q['uuid'] for q in m['questions']]+[q['uuid'] for q in review]
        self.assertEqual(len(ids),1030);self.assertEqual(len(set(ids)),1030)
        self.assertEqual({q['bucket'] for q in m['questions']},{b['key'] for b in m['buckets']})
        self.assertTrue(all(q['fingerprint'] and q['evidence'] for q in m['questions']))
        self.assertTrue(any(q['document_id']==17 and q['label']=='例2.3.5' and q['status']=='review' for q in review))
        self.assertEqual(_safe_drill_target('/analog-selected?tier=core',site='ei'),'/analog-selected?tier=core')

    def test_core_and_advanced_topics(self):
        row=classify('共射放大电路，求静态工作点并画微变等效，求增益和输入输出电阻')
        self.assertEqual(row['bucket'],'transistor');self.assertTrue(row['combined_static_dynamic'])
        self.assertEqual(classify('深度负反馈判断组态，求闭环增益')['bucket'],'feedback')
        self.assertEqual(classify('理想运放组成积分运算电路，求输出')['bucket'],'opamp')
        self.assertEqual(classify('差分放大器带电流源负载，求共模抑制比')['bucket'],'differential')
        self.assertEqual(classify('BJT米勒等效，求上限截止频率')['bucket'],'high_frequency')
        self.assertEqual(classify('求滞回比较器翻转阈值')['bucket'],'hysteresis')
        self.assertEqual(classify('OCL互补推挽功放求效率和最大功率')['bucket'],'power')

    def test_digital_mixed_unknown_and_concept_gates(self):
        self.assertEqual(classify('触发器与计数器逻辑函数')['status'],'excluded')
        self.assertEqual(classify('二极管与门的逻辑电路')['status'],'review')
        self.assertEqual(classify('CMOS反相器和共源放大电路比较')['status'],'review')
        self.assertEqual(classify('运放组成正弦波振荡器')['status'],'review')
        self.assertEqual(classify('',topic='共射放大电路')['status'],'review')
        self.assertEqual(classify('什么是负反馈',label='ANA-SA-12')['tier'],'foundation')
        self.assertEqual(classify('求运放闭环增益',label='2023年 · 选择1')['tier'],'foundation')
        self.assertEqual(classify('共射电路',scope='out_of_scope')['status'],'review')
        self.assertEqual(classify('带宽20MHz的模拟信号A/D转换，求分辨率')['status'],'review')
        self.assertEqual(classify('理想运放比较器，求传输特性')['status'],'review')
        self.assertEqual(classify('选择正确答案填入空内，集成运放采用差分输入级')['tier'],'foundation')
        self.assertEqual(classify('集成运放组成及各级作用',topic='集成运放组成',source='local_crop_ocr_with_reviewed_topic')['tier'],'foundation')


class AnalogCollectionTests(CollectionFixture):
    def setUp(self):
        super().setUp()
        m={'title':'模电严选','basis':'Study priorities','inventory_count':4,'questions':self.rows,
           'buckets':[dict(key=k,title=k,rank=i,tier='core',focus='Practice') for i,k in enumerate(['first_order','thevenin'],1)]}
        for target,value in [('drill.analog_selected.manifest',m),('drill.analog_selected_views.manifest',m),
                             ('drill.analog_selected_views.review_manifest',{'records':[]})]:
            p=patch(target,return_value=value);p.start();self.addCleanup(p.stop)

    def get(self,query='',*,view=AnalogSelectedView,question=None,user=None,host='ei.test'):
        return super().get(query.replace('collection=circuit_selected','collection=analog_selected'),view=view,question=question,user=user,host=host)

    def test_navigation_is_not_affected_by_signal_collection(self):
        with patch('drill.signal_selected.manifest',return_value={'questions':[],'buckets':[]}):
            result=self.get('collection=analog_selected&bucket=first_order',view=DrillQuestionDetailView,question=self.q1)
            self.assertEqual(result.data['next_question_uuid'],str(self.q2.uuid))

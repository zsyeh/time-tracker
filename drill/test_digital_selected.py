from unittest.mock import patch
from django.test import SimpleTestCase

from .digital_selected import manifest, review_manifest
from .digital_selected_views import DigitalSelectedView
from .digital_selection_rules import classify
from .test_circuit_selected import CircuitCollectionTests as CollectionFixture
from .views import DrillQuestionDetailView
from .web_views import _safe_drill_target


class DigitalRuleTests(SimpleTestCase):
    def test_partition_and_reference_integrity(self):
        m=manifest();r=review_manifest()['records']
        ids=[q['uuid'] for q in m['questions']]+[q['uuid'] for q in r]
        self.assertEqual(len(ids),952);self.assertEqual(len(set(ids)),952)
        self.assertEqual({q['bucket'] for q in m['questions']},{b['key'] for b in m['buckets']})
        self.assertTrue(all(q['fingerprint'] and q['evidence'] for q in m['questions']))
        self.assertEqual(_safe_drill_target('/digital-selected?kind=design',site='ei'),'/digital-selected?kind=design')

    def test_standard_analysis_design_and_chip_applications(self):
        self.assertEqual(classify('同步时序电路由D触发器构成，写出状态方程、状态表')['bucket'],'sync_analysis')
        self.assertEqual(classify('分析逻辑电路的功能，写出逻辑表达式，列出真值表，卡诺图化简')['bucket'],'comb_analysis')
        self.assertEqual(classify('设计三人表决器，列出真值表')['bucket'],'comb_design')
        self.assertEqual(classify('用JK触发器设计简单同步模6计数器，求状态编码和激励方程')['bucket'],'sync_design')
        self.assertEqual(classify('用74LS161设计十进制计数器')['bucket'],'counter')
        self.assertEqual(classify('用8选1数据选择器实现逻辑函数')['bucket'],'mux')
        self.assertEqual(classify('用74138译码器实现逻辑函数')['bucket'],'decoder')
        self.assertEqual(classify('触发器电压波形如图，求D触发器下一状态')['bucket'],'flipflop')

    def test_scope_and_priority_false_positives(self):
        self.assertEqual(classify('理想运放组成电压比较器')['status'],'review')
        self.assertNotEqual(classify('输入失调电压越大表明运放输入差分级失配越严重还是功耗越大')['status'],'included')
        self.assertEqual(classify('用Verilog HDL描述4选1数据选择器')['status'],'review')
        self.assertEqual(classify('74LS138地址译码，求地址范围')['status'],'review')
        self.assertEqual(classify('设计异步时序电路')['status'],'review')
        self.assertEqual(classify('多片74LS161级联计数器分析')['tier'],'cross')
        self.assertEqual(classify('简述组合逻辑设计流程',label='DIG-SA-09')['tier'],'foundation')
        self.assertEqual(classify('分析电路，写出逻辑函数并说明电路功能特点')['kind'],'analysis')
        self.assertEqual(classify('计算补码运算')['bucket'],'logic_basics')
        self.assertEqual(classify('CMOS门电路噪声容限和扇出系数')['tier'],'cross')
        self.assertEqual(classify('',topic='同步时序电路')['status'],'review')
        self.assertEqual(classify('此题图缺失，T触发器构成的同步时序电路')['status'],'review')
        self.assertEqual(classify('化简多输出逻辑函数，尽量利用共用项')['bucket'],'logic_basics')
        self.assertEqual(classify('试用列真值表的方法证明下列异或运算公式')['tier'],'foundation')
        self.assertEqual(classify('列出下列逻辑函数的真值表')['bucket'],'logic_basics')
        self.assertEqual(classify('已知逻辑函数的波形图，试求真值表和逻辑函数式')['bucket'],'logic_basics')
        self.assertEqual(classify('画出由与非门组成的SR锁存器的输出电压波形')['bucket'],'flipflop')
        self.assertEqual(classify('用数据选译器实现三开关控制电灯逻辑电路')['bucket'],'mux')
        self.assertEqual(classify('OD输出与非门接成线与结构，写出逻辑函数并计算外接电阻允许范围')['bucket'],'electrical')
        rows={q['label']:q for q in manifest()['questions'] if q['document_id']==20}
        for label in ['课后题 2.1','课后题 2.3','课后题 2.5','课后题 2.8']:
            self.assertEqual(rows[label]['tier'],'foundation')
        for label in ['课后题 5.1','课后题 5.2']:
            self.assertEqual(rows[label]['bucket'],'flipflop')
        self.assertEqual(rows['课后题 4.21']['bucket'],'mux')
        self.assertEqual(rows['课后题 3.10']['tier'],'cross')


class DigitalCollectionTests(CollectionFixture):
    def setUp(self):
        super().setUp()
        self.rows[0]['kind']='design'
        self.data={'title':'数电严选','basis':'Study priorities','inventory_count':4,'questions':self.rows,
                   'kinds':['design','analysis','calculation','concept'],
                   'buckets':[dict(key=k,title=k,rank=i,tier='core',focus='Practice') for i,k in enumerate(['first_order','thevenin'],1)]}
        for target,value in [('drill.digital_selected.manifest',self.data),('drill.digital_selected_views.manifest',self.data),
                             ('drill.digital_selected_views.review_manifest',{'records':[]})]:
            p=patch(target,return_value=value);p.start();self.addCleanup(p.stop)

    def get(self,query='',*,view=DigitalSelectedView,question=None,user=None,host='ei.test'):
        return super().get(query.replace('collection=circuit_selected','collection=digital_selected'),view=view,question=question,user=user,host=host)

    def test_design_filter_and_collection_isolation(self):
        self.assertEqual(self.get('kind=design').data['progress']['total'],1)
        with patch('drill.analog_selected.manifest',return_value={'questions':[],'buckets':[]}):
            detail=self.get('collection=digital_selected&kind=design',view=DrillQuestionDetailView,question=self.q1).data
            self.assertIsNone(detail['next_question_uuid'])
        with patch('drill.circuit_selected.manifest',return_value=self.data):
            self.assertEqual(self.get('kind=unsupported').status_code,404)

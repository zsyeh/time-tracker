"""892 analog study priorities; conservative stem rules, never probabilities."""
import re

BUCKETS = [
    ('transistor', '共射／共源 · 静态与小信号', 'core', '静态工作点、工作区、交流等效；增益及输入输出电阻。'),
    ('feedback', '深度负反馈 · 组态与闭环增益', 'core', '反馈极性、四种组态、反馈系数与深度负反馈近似。'),
    ('opamp', '集成运放 · 比例、加减与积分', 'core', '理想运放虚短虚断、串级运算与输入输出关系。'),
    ('differential', '差分放大／电流源负载', 'advanced', '静态电流、差模共模增益、共模抑制比及有源负载。'),
    ('high_frequency', '高频小信号／米勒／上限频率', 'advanced', '结电容、米勒等效、极点和上限截止频率；与中频分析衔接。'),
    ('multistage', '多级放大 · 增益与输入输出电阻', 'advanced', '级间负载效应、总增益和输入输出电阻。'),
    ('hysteresis', '滞回比较器 · 阈值与传输特性', 'advanced', '上下翻转阈值、回差和电压传输曲线。'),
    ('power', 'OCL／互补推挽 · 功率与效率', 'foundation', '输出功率、效率、交越失真和晶体管耗散。'),
    ('diode', '二极管 · 分段线性模型', 'foundation', '导通截止判断、恒压降和小信号模型，不主攻器件物理。'),
]
PATTERNS = {
    'transistor': r'共[射源集基漏栅]|射极跟随|源极跟随|静态工作点|微变等效|小信号等效|[BJ]FET|MOSFET|BJT|晶体管.{0,14}(?:放大|工作区|小信号|微变)|三极管.{0,14}(?:放大|工作区)|场效应管.{0,14}(?:放大|小信号)',
    'feedback': r'负反馈|反馈.{0,3}(?:组态|极性|系数)|闭环增益|闭环放大倍数|电压串联|电流串联|电压并联|电流并联',
    'opamp': r'运算放大器|集成运放|理想运放|运放|(?:反相|同相|比例|求和|加减|积分|微分)运算电路|虚短|虚断',
    'differential': r'差[分动].{0,8}(?:放大|电路|增益)|差模|共模抑制|共模增益|共模放大|电流源负载|电流源电路|有源负载|尾电流|恒流源|电流镜',
    'high_frequency': r'高频.{0,10}(?:小信号|等效|模型|响应|分析)|频率响应|米勒|密勒|Miller|上限.{0,4}频率|上截止|结电容|通频带|带宽|波特图',
    'multistage': r'多级放大|两级放大|二级放大|级间.{0,8}(?:耦合|负载)|各级.{0,10}增益',
    'hysteresis': r'滞回|回差|施密特|Schmitt|翻转阈值|上下.{0,5}阈值',
    'power': r'功率放大|功放|OCL|互补推挽|乙类|甲乙类|交越失真|最大输出功率|转换效率',
    'diode': r'二极管|恒压降|分段线性|限幅电路|钳位电路',
}
DIGITAL = r'触发器|卡诺|逻辑函数|逻辑门|真值表|计数器|译码器|编码器|逻辑表达式|状态转换表|存储器|竞争.{0,3}冒险|同步时序|组合逻辑|数字电路|数电|与非门|或非门|二极管与门|TTL门|CMOS反相器|A[/／-]D|D[/／-]A|ADC|DAC|模数转换|数模转换|转换芯片'
EXTRA = r'锁相环|晶体振荡|正弦波振荡|模拟乘法器|乘法运算|LC振荡|RC振荡|文氏桥|单稳态|多谐振荡|多谐振|矩形波发生|三角波发生|锯齿波发生'


def normalize(text):
    return re.sub(r'\s+', '', text)


def classify(stem, *, label='', topic='', scope='', source='structured_text'):
    text = normalize(stem)
    tags = [k for k,p in PATTERNS.items() if re.search(p,text,re.I)]
    result = dict(status='review',bucket=None,tags=tags,tier='foundation',kind='calculation',
                  combined_static_dynamic=False, reason=[])
    if not text:
        result['reason']=['缺少可靠题干，不能只按章号归类']; return result
    if re.search(DIGITAL,text,re.I):
        result.update(status='review' if tags else 'excluded',reason=['数电或数模混合内容，不直接纳入模电严选']); return result
    if scope=='out_of_scope' or re.search(EXTRA,text,re.I):
        result['reason']=['超纲标记或非本轮目标题型的扩展内容，待复核']; return result
    if '比较器' in text and 'hysteresis' not in tags:
        result['reason']=['普通/窗口比较器或图中滞回未确认，不当作线性运放综合题']; return result
    if source=='cached_local_ocr' and len(re.findall(r'(?:^|\n)\s*\d{1,2}[、．.]',stem))>1:
        result['reason']=['缓存区段存在多个主题号，归属待复核']; return result
    if not tags:
        result.update(status='review' if 'ocr' in source else 'excluded',reason=['未可靠命中九类指定考点，不猜图中电路类型']); return result
    primary=next(k for k in ['hysteresis','feedback','differential','high_frequency','power','opamp','multistage','transistor','diode'] if k in tags)
    if 'power' in tags and re.search(r'最大.{0,4}输出功率|转换效率|OCL|互补推挽',text,re.I):
        primary='power'
    # Per-question concept markers must not masquerade as calculation topics.
    concept=('填空' in label or '选择' in label or '判断' in label or '背诵' in topic
             or bool(re.search(r'SA-\d|简答',label))
             or (source=='local_crop_ocr_with_reviewed_topic' and bool(re.search(r'概念|定性|组成|参数与选用|反馈判断|负反馈引入|类型与工作状态|接法与性能',topic)))
             or bool(re.search(r'选择.{0,8}(?:正确|合适).{0,6}答案|什么是|何谓|简述|简要说明|说明.{0,12}(?:特点|原理|作用|条件|区别|概念)|主要适用|基本概念|参数与选用|定性分析',text)))
    result.update(status='included',bucket=primary,kind='concept' if concept else 'calculation',
                  tier='foundation' if concept else next(b[2] for b in BUCKETS if b[0]==primary),
                  combined_static_dynamic='transistor' in tags and bool(re.search(r'静态|工作点|偏置',text))
                  and bool(re.search(r'小信号|微变|交流|动态|增益|放大倍数|输入电阻|输出电阻',text)),
                  reason=['题干/逐题已审考点匹配：'+'、'.join(tags)])
    return result

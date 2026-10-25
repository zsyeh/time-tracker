"""Deterministic digital priorities. S/A/B/C are study tiers, not odds."""
import re

BUCKETS = [
    ('sync_analysis','同步时序分析 · 状态方程、表与图','core','写驱动/状态方程、状态转换表与状态图，判断功能。'),
    ('comb_analysis','组合逻辑分析 · 表达式、真值表与功能','core','由门电路求函数，化简、列真值表并判断功能。'),
    ('comb_design','组合逻辑设计 · 真值表、化简与电路','core','表决器、奇偶校验等；从题意建模并画逻辑电路。'),
    ('sync_design','简单同步时序设计 · 编码与激励','advanced','选择触发器、状态编码和激励方程；不主攻复杂专用时序。'),
    ('mux','MUX 数据选择器实现函数','advanced','4选1、8选1与74151/74153的逻辑函数实现。'),
    ('decoder','编码器／译码器应用','advanced','74138等中规模器件的功能与逻辑实现。'),
    ('counter','计数器应用 · 74161／74163','advanced','模数、清零、置数和状态循环；芯片专项排在前三类之后。'),
    ('flipflop','D／JK／T 触发器与波形','advanced','特性/激励方程、下一状态与波形，注意触发时刻。'),
    ('adder_comparator','加法器／比较器','foundation','半加器、全加器和多位数字比较器分析设计。'),
    ('hazard','竞争冒险 · 判断与消除','foundation','静态冒险、冗余项与消除方法。'),
    ('cmos','CMOS 门网络逻辑分析','foundation','上拉/下拉网络、反相器、与非/或非及三态门逻辑。'),
    ('logic_basics','卡诺图／补码／逻辑基础','foundation','含无关项化简、数制、原反补码和基本逻辑运算。'),
    ('shift_register','移位寄存器／简单序列','cross','移位过程、串并转换与简单序列发生。'),
    ('electrical','门电路电气特性','cross','噪声容限、扇出、传播延迟、驱动能力和功耗。'),
]
PATTERNS = {
    'sync_analysis':r'同步时序|状态(?:方程|转换表|转换图|转移表|转移图|表|图)|次态方程|驱动方程|激励方程',
    'comb_analysis':r'组合逻辑|组合电路|逻辑表达式|逻辑函数|真值表|与非门|或非门|逻辑电路',
    'comb_design':r'表决器|投票|奇偶校验|奇偶检测',
    'sync_design':r'设计.{0,15}(?:同步|时序)|状态编码|状态分配',
    'counter':r'计数器|计数电路|计数功能|74(?:LS|HC|HCT)?(?:161|163|160|162|90|92|93)|模[Nn\d一二三四五六七八九十]+计数',
    'mux':r'数据选择器|多路选择器|MUX|[24816]+选[1一]|74(?:LS|HC)?(?:151|153|157)',
    'decoder':r'编码器|译码器|译码电路|74(?:LS|HC)?(?:138|139|148|154)',
    'flipflop':r'触发器|[DJKTRS]+.{0,3}触发|特性方程|激励表',
    'adder_comparator':r'加法器|半加器|全加器|数字比较器|数值比较器|比较.{0,5}(?:大小|器)|74(?:LS|HC)?(?:283|85)',
    'hazard':r'竞争|冒险|冗余项',
    'cmos':r'CMOS|MOS门|上拉网络|下拉网络|三态门|漏极开路|OD门',
    'logic_basics':r'卡诺图|化简|最小项|最大项|补码|反码|原码|进制|无关项|最简.{0,6}(?:与或|或与|逻辑)|逻辑代数|摩根|逻辑变量|逻辑运算',
    'shift_register':r'移位寄存器|移位过程|串并转换|序列发生器|序列信号发生|顺序脉冲|74(?:LS|HC)?(?:194|195)',
    'electrical':r'噪声容限|噪声容[量限]|扇出|扇入|传播延迟|传输延迟|传输时间|功耗|驱动能力|噪声裕量|电气特性',
}
ANALOG=r'深度负反馈|放大器|放大电路|集电极|基极|发射极|小信号等效|运算放大器|理想运放|功率放大|米勒效应|OCL|电压比较器|滞回|共模抑制'
EXTRA=r'异步时序|锁相环|微程序|动态RAM|动态存储器|地址扩展|存储器扩展|地址译码|乘法阵列|流水线|复杂级联|Verilog|VHDL|HDL|FPGA|CPLD|题目不全|图缺失|缺图|图不全|条件不全|题干不全|单稳态|多谐振荡'


def classify(stem,*,label='',topic='',scope='',source='structured_text'):
    text=re.sub(r'\s+','',stem)
    tags=[k for k,p in PATTERNS.items() if re.search(p,text,re.I)]
    row=dict(status='review',bucket=None,tags=tags,tier='foundation',kind='analysis',combined_standard=False,reason=[])
    if not text:
        row['reason']=['缺少可靠题干，不按章节号猜题型'];return row
    if scope=='out_of_scope' or re.search(EXTRA,text,re.I):
        row['reason']=['超纲标记或非本轮简单设计深度的扩展内容'];return row
    if re.search(ANALOG,text,re.I):
        row.update(status='review' if tags else 'excluded',reason=['模电或数模混合题，不直接混入数电严选']);return row
    if source=='cached_local_ocr' and len(re.findall(r'(?:^|\n)\s*(?:\d{1,2}|[一二三四五六七八九十]+)\s*[、．.]',stem))>1:
        row['reason']=['OCR区段含多个主题号，题意归属待核对'];return row
    if not tags:
        row.update(status='review' if 'ocr' in source else 'excluded',reason=['未可靠命中指定数电题型']);return row
    design=bool(re.search(r'设计|实现.{0,15}(?:逻辑函数|函数|计数|电路|状态)|构成.{0,15}(?:计数器|时序电路|组合电路)',text))
    # A chip counter application is not automatically a state-machine design.
    chip=bool(re.search(r'74(?:LS|HC|HCT)?(?:161|163|160|162|90|92|93)',text,re.I))
    if 'shift_register' in tags:primary='shift_register'
    elif 'counter' in tags and (chip or not design):primary='counter'
    elif design and ('sync_design' in tags or ('flipflop' in tags and ('sync_analysis' in tags or 'counter' in tags))):primary='sync_design'
    elif 'counter' in tags:primary='counter'
    elif 'mux' in tags:primary='mux'
    elif 'decoder' in tags:primary='decoder'
    elif 'adder_comparator' in tags:primary='adder_comparator'
    elif 'hazard' in tags:primary='hazard'
    elif 'electrical' in tags:primary='electrical'
    elif 'cmos' in tags:primary='cmos'
    elif 'sync_analysis' in tags and ('flipflop' in tags or '时序' in text or '状态' in text):primary='sync_analysis'
    elif 'flipflop' in tags:primary='flipflop'
    elif 'comb_design' in tags or (design and 'comb_analysis' in tags):primary='comb_design'
    elif 'comb_analysis' in tags and re.search(r'分析.{0,30}(?:电路|逻辑)|电路.{0,35}(?:逻辑功能|真值表|输出|函数)',text):primary='comb_analysis'
    elif 'logic_basics' in tags:primary='logic_basics'
    else:primary='comb_analysis'
    concept=('选择' in label or '填空' in label or '判断' in label or '背诵' in topic
             or bool(re.search(r'SA-\d|简答',label))
             or (bool(re.search(r'什么是|何谓|简述|简要说明|选择.{0,8}正确.{0,6}答案|说明.{0,12}(?:特点|原理|区别|概念)',text))
                 and not re.search(r'写出|画出|计算|列出|求出',text)))
    kind='concept' if concept else 'design' if design else 'calculation' if primary in {'logic_basics','electrical'} else 'analysis'
    row.update(status='included',bucket=primary,tier='foundation' if concept else next(b[2] for b in BUCKETS if b[0]==primary),kind=kind,
               combined_standard=primary in {'sync_analysis','comb_analysis','comb_design','sync_design','mux','decoder','counter'} and not concept,
               reason=['题干明确匹配：'+'、'.join(tags)])
    if primary=='counter' and re.search('级联|多片|多级',text):
        row.update(tier='cross',combined_standard=False,reason=['计数器级联专项降至C选练，不当作最高优先级'])
    return row

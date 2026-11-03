"""Complete 892 circuit/analog/digital/communications formula bank.

The canonical Markdown is kept verbatim in ``drill/data``.  This module only
turns each displayed equation into a deterministic review item, so the UI can
quiz a small daily subset without shortening the underlying knowledge bank.
"""

from __future__ import annotations

import re
from pathlib import Path

from .signal_formula_library import START_DATE


SOURCE_PATH = Path(__file__).parent / "data" / "892_four_subject_formula_library.md"

SUBJECTS = {
    "circuit": {"letter": "A", "name": "电路原理", "collection": "circuit_selected", "route": "/circuit-selected"},
    "analog": {"letter": "B", "name": "模拟电子技术", "collection": "analog_selected", "route": "/analog-selected"},
    "digital": {"letter": "C", "name": "数字电子技术", "collection": "digital_selected", "route": "/digital-selected"},
    "communication": {"letter": "D", "name": "通信原理", "collection": "communication_selected", "route": "/communication-selected"},
}

SECTION_CONDITIONS = {
    "A1": "采用明确的电压、电流参考方向；功率正负按关联参考方向。电容电压和电感电流连续式要求不存在相应理想冲激激励。",
    "A2": "必须先核对实际拓扑、节点和支路方向；含理想电压源时使用超节点或补充约束方程。",
    "A3": "适用于线性端口；含受控源时保留受控源并用测试源求等效电阻。最大功率式要求等效电阻为正。",
    "A4": "一阶式用于开关后参数不变的线性一阶电路；等效电阻需将独立源置零并保留受控源。串联、并联 RLC 的衰减系数不可混用。",
    "A5": "正弦稳态采用 RMS 相量；复功率和最大功率式须遵守参考方向与负载模型。谐振式限定理想串／并联单一损耗模型。",
    "B1": "二极管处于所用指数模型适用区，小信号电阻在给定静态工作点线性化。",
    "B2": "先确认 BJT 工作在放大区并建立静态工作点；增益式仅在题设的旁路、负载及忽略参数假设下成立。",
    "B3": "先确认器件极性与工作区；长沟道平方律、忽略沟道长度调制和匹配电流镜均是近似模型。",
    "B4": "差分对要求两管对称、理想尾电流源及指定输出定义；多级乘积中每一级必须已计入下一级负载。",
    "B5": "A 与 F 的定义、方向和量纲必须一致；电压／电流指输出取样，串联／并联指输入混合。",
    "B6": "一阶 Bode 式用于相应实零极点模型；负常数及复共轭零极点需另计相位和二阶项。",
    "B7": "虚短、虚断只用于理想运放在线性负反馈且未饱和时；比较器和振荡器必须按实际阈值与拓扑分析。",
    "C1": "位数和基数必须固定；补码范围与溢出判断针对 n 位有符号运算。",
    "C2": "变量取二值逻辑；SOP、POS、无关项及门级实现必须保持原逻辑函数等价。",
    "C3": "输入输出有效电平和器件定义需明确；冒险消除式针对对应两级结构和路径延迟。",
    "C4": "功耗、延迟与噪声容限式为给定 CMOS 负载及一阶模型；上下拉网络结构需按门型判断。",
    "C5": "必须确认触发器类型、同步／异步控制、有效电平和触发沿；SR 式受禁止输入约束。",
    "C6": "同步时序式基于统一时钟；最高频率与保持约束须同时检查组合路径、建立保持时间及可能的时钟偏斜。",
    "D1": "概率归一且对数以 2 为底；带宽、功率与 N0 的单／双边定义必须和 AWGN 模型一致。",
    "D2": "信号严格带限并满足采样条件；量化噪声式基于均匀误差模型，SQNR 近似针对满幅正弦和理想均匀量化。",
    "D3": "区分标准 AM、DSB-SC、SSB 与 VSB；幅度规范、频率变量和基带带宽定义必须与题设一致。",
    "D4": "FM 式中的 kf 按 rad/s/幅度定义；Carson 式是单音调制带宽近似。PM 瞬时频率取决于消息导数。",
    "D5": "综合脉冲响应在抽样时刻满足第一奈奎斯特准则；带宽均按所注明的单边基带定义。",
    "D6": "波形、正交条件、检测方式和能量定义必须匹配；M 进制比特率式不含额外信道编码开销。",
    "D7": "误码率式限定 AWGN、相应先验概率及相干／非相干最佳检测模型；不同模型不可混用。",
    "D8": "匹配滤波器针对指定采样时刻和已知信号；复信号需共轭，最大信噪比是判决抽样点处的量。",
}

SECTION_PITFALLS = {
    "A1": "不要忽略参考方向，也不要在无条件时强行令储能变量连续。",
    "A2": "Y-Δ 比例和电桥平衡条件不能脱离拓扑机械套用。",
    "A3": "受控源不能置零，叠加定理也不能直接叠加功率。",
    "A4": "串联与并联 RLC 的 α 不通用，初值必须取 0+。",
    "A5": "峰值与 RMS、串联与并联的 Q 和带宽、同名端符号最易混淆。",
    "B1": "热电压、理想因子和静态电流必须对应同一工作点。",
    "B2": "不能把忽略 ro、无交流退化的增益式当成所有共射电路通式。",
    "B3": "平方律只在指定饱和区成立，JFET 极性和 VP 符号必须检查。",
    "B4": "单端与双端差模增益相差 2 倍，输出侧还决定符号。",
    "B5": "≈1/F 不能脱离反馈组态和量纲直接当作电压增益。",
    "B6": "幅度用 20 log，功率用 10 log；相位在拐点附近渐变而非跳变。",
    "B7": "正反馈或饱和时不能使用虚短；振荡周期不是任意波形发生器通式。",
    "C1": "补码溢出不是简单丢弃最高进位，要检查同号相加异号或符号位进出位。",
    "C2": "卡诺图只能合并 2 的整数次幂个相邻格，无关项可以用但不必覆盖。",
    "C3": "译码器有效电平不同会整体反相；共识项只消除对应静态冒险。",
    "C4": "与非门和或非门的 NMOS/PMOS 串并联关系不要写反。",
    "C5": "不同有效电平的 SR 锁存器禁止组合不同，必须看器件定义。",
    "C6": "建立时间决定最长路径，保持时间检查最短路径，两者不能互相替代。",
    "D1": "功率比 dB 与幅度比 dB 系数不同，N0 单边／双边定义不能混用。",
    "D2": "采样率、量化位数和 PCM 比特率的单位不同，临界采样不能无条件取等号。",
    "D3": "DSB-SC 没有离散载波线，AM 总功率不能只算边带。",
    "D4": "FM 的调频指数与最大频偏单位必须先统一，FM 与 PM 的瞬时频率关系不同。",
    "D5": "Rb、Rs、单边 B 和滚降系数 α 的关系不可混用带通带宽定义。",
    "D6": "2FSK 最小频差依赖相位、符号区间与正交条件，并非所有 FSK 的通式。",
    "D7": "BPSK、相干 2FSK 和非相干 2FSK 的 Q 函数或指数式不可互换。",
    "D8": "不能漏掉共轭、时间反转和采样时刻位移。",
}

SUBJECT_PRINCIPLES = {
    "circuit": "先确定拓扑、参考方向和工作状态，再由 KCL/KVL、等效或动态方程建立模型。",
    "analog": "先求静态工作点和工作区，再在线性化模型及明确负载条件下计算。",
    "digital": "先固定逻辑约定与状态定义，再用布尔等价、器件方程或时序约束推导。",
    "communication": "先统一信号、带宽、能量和噪声谱密度定义，再选择对应调制或检测模型。",
}


def _clean_title(value: str) -> str:
    return value.strip().replace("**", "").replace("`", "")


def _parse_library():
    text = SOURCE_PATH.read_text(encoding="utf-8")
    subject_by_letter = {meta["letter"]: key for key, meta in SUBJECTS.items()}
    headings = list(re.finditer(r"^# ([A-D])\. ([^\n]+)$", text, re.MULTILINE))
    entries = []
    counts = {}
    for heading_index, heading in enumerate(headings):
        letter = heading.group(1)
        subject = subject_by_letter[letter]
        end = headings[heading_index + 1].start() if heading_index + 1 < len(headings) else len(text)
        block = text[heading.end():end]
        sections = list(re.finditer(r"^### ([A-D]\d+)\. ([^\n]+)$", block, re.MULTILINE))
        for section_index, section_match in enumerate(sections):
            section = section_match.group(1)
            section_end = sections[section_index + 1].start() if section_index + 1 < len(sections) else len(block)
            section_text = block[section_match.end():section_end]
            formulas = [
                re.sub(r"\s+", " ", value.strip()).replace(r"\mathrm{补}", r"\mathrm{comp}")
                for value in re.findall(r"\$\$(.*?)\$\$", section_text, re.DOTALL)
            ]
            counts[subject] = counts.get(subject, 0) + len(formulas)
            title = _clean_title(section_match.group(2))
            for formula_index, formula in enumerate(formulas, 1):
                entries.append({
                    "key": f"four_{subject}_{section.lower()}_{formula_index:02d}",
                    "section": section,
                    "subject": subject,
                    "subject_name": SUBJECTS[subject]["name"],
                    "title": f"{title} · {formula_index}/{len(formulas)}",
                    "formulas": (formula,),
                    "condition": SECTION_CONDITIONS[section],
                    "principle": SUBJECT_PRINCIPLES[subject],
                    "pitfall": SECTION_PITFALLS[section],
                    "tags": (subject, section.lower()),
                })
    expected = {"circuit": 77, "analog": 72, "digital": 55, "communication": 64}
    if counts != expected:
        raise RuntimeError(f"Incomplete 892 four-subject formula library: {counts!r}")
    return tuple(entries), counts


FORMULA_LIBRARY, FORMULA_COUNTS = _parse_library()
FORMULA_BY_KEY = {entry["key"]: entry for entry in FORMULA_LIBRARY}

CYCLE = (
    {
        **SUBJECTS["circuit"], "subject": "circuit",
        "title": "电路原理",
        "mistakes": ("受控源求端口等效时不能关闭受控源。", "开路电压、短路电流和测试源法要先核对端口定义。", "串联／并联 RLC 的 α、Q、Δω 不可混用。"),
    },
    {
        **SUBJECTS["analog"], "subject": "analog",
        "title": "模拟电子技术",
        "mistakes": ("先判断 BJT/MOS 工作区，再使用小信号公式。", "反馈组态决定闭环增益和反馈系数的量纲。", "Bode 图每个零极点的斜率与相位贡献要分别累计。"),
    },
    {
        **SUBJECTS["digital"], "subject": "digital",
        "title": "数字电子技术",
        "mistakes": ("补码溢出需检查符号位进位与出位。", "SOP/POS 与与非／或非两级实现不能混淆。", "时序电路必须同时检查建立时间与保持时间。"),
    },
    {
        **SUBJECTS["communication"], "subject": "communication",
        "title": "通信原理",
        "mistakes": ("功率 dB、幅度 dB 以及单／双边噪声谱定义要一致。", "标准 AM 与 DSB-SC 的载波和功率结构不同。", "无码间串扰、升余弦与匹配滤波的适用条件不可混用。"),
    },
)

DEFAULT_WEAK_KEYS = (
    "four_circuit_a3_05",
    "four_analog_b5_04",
    "four_digital_c2_18",
    "four_communication_d8_01",
)

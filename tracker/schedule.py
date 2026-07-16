"""Editable study-plan data rendered by the dashboard.

Keep schedule copy in this module so later timing or wording adjustments do not
require touching the dashboard template or its JavaScript.
"""

from copy import deepcopy


SUMMER_SCHEDULE = {
    'title': '暑假作息计划',
    'version': '2026 暑假 · 修正版',
    'subtitle': '考研优先 · 跑步与力量并行',
    'sleep_window': '23:00–06:30',
    'daily_study_target': '约 7 小时净学习（原计划口径）',
    'principle': '稳定执行优先于单日极限表现',
    'timeline': [
        {
            'time': '06:30',
            'title': '起床',
            'detail': '立即离床，接触自然光 20–30 分钟',
            'kind': 'routine',
        },
        {
            'time': '07:00',
            'title': '早餐与准备',
            'detail': '早餐、洗漱、整理当天任务',
            'kind': 'routine',
        },
        {
            'time': '07:30–10:00',
            'title': '数学核心',
            'detail': '新内容 / 难题 / 主线推进',
            'kind': 'study',
        },
        {
            'time': '10:20–12:00',
            'title': '892 专业课',
            'detail': '知识框架与例题',
            'kind': 'study',
        },
        {
            'time': '12:00–13:00',
            'title': '午餐与休息',
            'detail': '',
            'kind': 'break',
        },
        {
            'time': '13:00–15:00',
            'title': '数学练习或专业课训练',
            'detail': '',
            'kind': 'study',
        },
        {
            'time': '15:20–17:00',
            'title': '英语',
            'detail': '阅读、单词、错题整理',
            'kind': 'study',
        },
        {
            'time': '17:00–18:00',
            'title': '机动时间',
            'detail': '复盘、整理、生活事务',
            'kind': 'flex',
        },
        {
            'time': '18:00–19:00',
            'title': '晚餐',
            'detail': '',
            'kind': 'break',
        },
        {
            'time': '19:00–20:30',
            'title': '训练',
            'detail': '按周计划安排跑步 / 力量 / 游泳',
            'kind': 'training',
        },
        {
            'time': '20:30–21:00',
            'title': '恢复',
            'detail': '洗澡、拉伸、补充水分与碳水',
            'kind': 'recovery',
        },
        {
            'time': '21:00–22:00',
            'title': '轻复习',
            'detail': '背诵、错题、当日收束',
            'kind': 'study',
        },
        {
            'time': '22:00–22:30',
            'title': '低刺激放松',
            'detail': '时政长视频，禁止 Shorts / PUBG',
            'kind': 'routine',
        },
        {
            'time': '22:30–23:00',
            'title': '睡前准备',
            'detail': '洗漱、关屏、准备睡眠',
            'kind': 'routine',
        },
        {
            'time': '23:00',
            'title': '睡觉',
            'detail': '',
            'kind': 'sleep',
        },
    ],
    'weekly_training': [
        {'day': '周一', 'activity': '轻松跑 35–45 分钟 + 4–6 次短加速'},
        {'day': '周二', 'activity': '低容量力量：深蹲 / 卧推 / 硬拉'},
        {'day': '周三', 'activity': '休息，或轻松游泳 30–45 分钟'},
        {'day': '周四', 'activity': '质量跑：阈值与 VO₂max 隔周交替'},
        {'day': '周五', 'activity': '轻松跑 30–40 分钟'},
        {'day': '周六', 'activity': '长距离轻松跑 55–70 分钟'},
        {'day': '周日', 'activity': '完全休息或散步'},
    ],
    'study_quotas': [
        {'subject': '数学', 'duration': '3–3.5 h', 'focus': '主线、难题、错题'},
        {'subject': '专业课', 'duration': '2–2.5 h', 'focus': '892 系统推进'},
        {'subject': '英语', 'duration': '1–1.5 h', 'focus': '阅读 + 词汇'},
    ],
    'rules': [
        '固定 06:30 起床，不因晚睡推迟；午睡不超过 20 分钟，且不晚于 15:00。',
        '力量训练保持大重量、低次数、极低容量；不以失败单次作为常规训练。',
        '跑步保留每周一次质量刺激，同时逐步建立长距离有氧能力。',
        '当天只设 3 个硬任务；完成后再进入娱乐时间。',
        '睡眠少于 6 小时：取消 PR、VO₂max 或其他高风险高强度训练。',
        '9 月以后调整为 23:00–07:00，保持睡眠窗口稳定。',
    ],
}


def get_summer_schedule():
    """Return an isolated copy for template or future API consumers."""

    return deepcopy(SUMMER_SCHEDULE)

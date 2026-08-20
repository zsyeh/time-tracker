import difflib
import re
from collections import defaultdict

from .cleaning import clean_topic_title


ANSWER_PDF_BY_DOCUMENT = {
    '极限': '极限答案册.pdf',
    '一元积分': '一元积分题库-答案.pdf',
    '线性代数': '线代1000题参考答案.pdf',
    '二重积分': '二重积分题库答案.pdf',
    '多元微分': '多元微分大观-答案.pdf',
    '微分方程': '微分方程大观-答案.pdf',
    '反常积分': '反常积分-答案.pdf',
    '一元微分': '一元微分大观-答案.pdf',
}


def heading_key(value):
    value = clean_topic_title(value or '')
    value = re.sub(r'^\s*类[一二三四五六七八九十]+\s*[:：]\s*', '', value)
    value = re.sub(r'^\s*(?:[A-Z]|[一二三四五六七八九十]+|\d+)[.、)）]\s*', '', value, flags=re.I)
    value = re.sub(r'(?:题库|大观|带答案|参考答案)$', '', value)
    return re.sub(r'[^0-9a-zA-Z\u4e00-\u9fff]+', '', value).lower()


def reference_key(value):
    value = (value or '').split('>>', 1)[0]
    value = re.sub(
        r'^\s*(?:[ivxlcdm]+|[a-z]|\(?\d+\)?)[.)、）]?\s*',
        '',
        value,
        flags=re.I,
    )
    for old, new in (
        ('🐙', ''), ('0.1w', '1000'), ('0.1W', '1000'),
        ('魔法练习册', '1000'), ('张老师1000', '1000'),
    ):
        value = value.replace(old, new)
    return re.sub(r'[^0-9a-zA-Z\u4e00-\u9fff]+', '', value).lower()


def toc_entries_by_page(toc):
    stack = {}
    pages = defaultdict(list)
    for level, title, page in toc:
        stack = {key: item for key, item in stack.items() if key < level}
        ancestors = tuple(stack[key][1] for key in sorted(stack))
        pages[page].append((title, ancestors))
        stack[level] = (level, title, page)
    return pages


class TopicMatcher:
    def __init__(self, topics):
        self.by_heading = defaultdict(list)
        self.paths = {}
        for topic in topics:
            self.by_heading[heading_key(topic.display_title or topic.title)].append(topic)
            self.paths[topic.pk] = self._path(topic)

    @staticmethod
    def _path(topic):
        path = []
        seen = set()
        cursor = topic
        while cursor is not None and cursor.pk not in seen:
            seen.add(cursor.pk)
            path.append(heading_key(cursor.display_title or cursor.title))
            cursor = cursor.parent
        return tuple(reversed(path))

    def _unique_for_ancestors(self, headings):
        keys = tuple(key for key in (heading_key(value) for value in headings) if key)
        for key in reversed(keys):
            candidates = self.by_heading.get(key, ())
            if len(candidates) == 1:
                return candidates[0]
            if len(candidates) > 1:
                ranked = sorted(
                    (
                        (sum(1 for value in self.paths[item.pk] if value in keys), item)
                        for item in candidates
                    ),
                    key=lambda pair: pair[0],
                    reverse=True,
                )
                if len(ranked) == 1 or ranked[0][0] > ranked[1][0]:
                    return ranked[0][1]
        return None

    def from_breadcrumb(self, source_label):
        segments = [part.strip() for part in (source_label or '').split('>>') if part.strip()]
        return self._unique_for_ancestors(segments)

    def from_toc_page(self, source_label, entries):
        target = reference_key(source_label)
        def similarity(title):
            candidate = reference_key(title)
            score = difflib.SequenceMatcher(None, target, candidate).ratio()
            if min(len(target), len(candidate)) >= 5 and (target in candidate or candidate in target):
                return max(score, 0.94)
            return score

        scored = sorted(
            (
                (similarity(title), title, ancestors)
                for title, ancestors in entries
                if reference_key(title)
            ),
            key=lambda item: item[0],
            reverse=True,
        )
        if scored and scored[0][0] >= 0.72:
            score, _title, ancestors = scored[0]
            topic = self._unique_for_ancestors(ancestors)
            if topic is not None:
                return topic, score
        resolved = {}
        for _title, ancestors in entries:
            topic = self._unique_for_ancestors(ancestors)
            if topic is not None:
                resolved[topic.pk] = topic
        if len(resolved) == 1:
            score = scored[0][0] if scored else 0.0
            return next(iter(resolved.values())), score
        return None, scored[0][0] if scored else 0.0

"""Analog study priorities over canonical questions; no database imports."""
from functools import lru_cache
import json
from pathlib import Path

from .circuit_selected import filter_collection as filter_reviewed_collection

CODE = 'analog_selected'


@lru_cache(maxsize=1)
def manifest():
    return json.loads((Path(__file__).parent / 'data/analog_selected_v1.json').read_text())


@lru_cache(maxsize=1)
def review_manifest():
    return json.loads((Path(__file__).parent / 'data/analog_selected_review_v1.json').read_text())


def filter_collection(queryset, request, *, force=False):
    return filter_reviewed_collection(queryset, request, force=force, data=manifest(), code=CODE)

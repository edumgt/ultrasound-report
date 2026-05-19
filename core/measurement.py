from __future__ import annotations

import re
from typing import List

UNIT_MAP = {
    '센티미터': 'cm',
    '센티': 'cm',
    'cm': 'cm',
    '밀리미터': 'mm',
    '밀리': 'mm',
    'mm': 'mm',
}

DIMENSION_RE = re.compile(
    r'(?:약\s*)?(\d+(?:\.\d+)?)\s*(?:x|×|by|X)\s*(\d+(?:\.\d+)?)\s*'
    r'(센티미터|센티|cm|밀리미터|밀리|mm)',
    re.IGNORECASE,
)
SINGLE_RE = re.compile(
    r'(?:약\s*)?(\d+(?:\.\d+)?)\s*(센티미터|센티|cm|밀리미터|밀리|mm)',
    re.IGNORECASE,
)


def _normalize_unit(unit: str) -> str:
    return UNIT_MAP.get(unit.lower(), unit.lower())


def normalize_measurements(text: str) -> str:
    def replace_dim(match: re.Match[str]) -> str:
        first, second, unit = match.groups()
        return f'{first}×{second}{_normalize_unit(unit)}'

    normalized = DIMENSION_RE.sub(replace_dim, text)

    def replace_single(match: re.Match[str]) -> str:
        value, unit = match.groups()
        return f'{value}{_normalize_unit(unit)}'

    return SINGLE_RE.sub(replace_single, normalized)


def extract_measurements(text: str) -> List[str]:
    normalized = normalize_measurements(text)
    matches = []
    for match in re.finditer(r"\b\d+(?:\.\d+)?(?:×\d+(?:\.\d+)?)?(?:mm|cm)\b", normalized):
        token = match.group(0)
        if token not in matches:
            matches.append(token)
    return matches

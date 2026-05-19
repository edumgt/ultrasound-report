from __future__ import annotations

import re
from typing import List

UNIT_MAP = {
    "센티미터": "cm",
    "센티": "cm",
    "cm": "cm",
    "밀리미터": "mm",
    "밀리": "mm",
    "mm": "mm",
}
NUMBER_TOKEN_RE = re.compile(r"^\d+(?:\.\d+)?$")
COMBINED_DIMENSION_RE = re.compile(r"^(\d+(?:\.\d+)?)(?:x|×|by|X)(\d+(?:\.\d+)?)(센티미터|센티|cm|밀리미터|밀리|mm)$", re.IGNORECASE)
COMBINED_SINGLE_RE = re.compile(r"^(\d+(?:\.\d+)?)(센티미터|센티|cm|밀리미터|밀리|mm)$", re.IGNORECASE)


def _normalize_unit(unit: str) -> str:
    return UNIT_MAP.get(unit.lower(), unit.lower())


def normalize_measurements(text: str) -> str:
    tokens = text.split()
    normalized: List[str] = []
    i = 0

    while i < len(tokens):
        token = tokens[i]

        if token == "약":
            i += 1
            continue

        dim_match = COMBINED_DIMENSION_RE.match(token)
        if dim_match:
            first, second, unit = dim_match.groups()
            normalized.append(f"{first}×{second}{_normalize_unit(unit)}")
            i += 1
            continue

        single_match = COMBINED_SINGLE_RE.match(token)
        if single_match:
            value, unit = single_match.groups()
            normalized.append(f"{value}{_normalize_unit(unit)}")
            i += 1
            continue

        next_token = tokens[i + 1] if i + 1 < len(tokens) else ""
        third_token = tokens[i + 2] if i + 2 < len(tokens) else ""
        fourth_token = tokens[i + 3] if i + 3 < len(tokens) else ""

        if NUMBER_TOKEN_RE.match(token) and next_token in {"x", "×", "by", "X"} and NUMBER_TOKEN_RE.match(third_token) and fourth_token.lower() in UNIT_MAP:
            normalized.append(f"{token}×{third_token}{_normalize_unit(fourth_token)}")
            i += 4
            continue

        if NUMBER_TOKEN_RE.match(token) and next_token.lower() in UNIT_MAP:
            normalized.append(f"{token}{_normalize_unit(next_token)}")
            i += 2
            continue

        normalized.append(token)
        i += 1

    return " ".join(normalized)


def extract_measurements(text: str) -> List[str]:
    normalized = normalize_measurements(text)
    matches: List[str] = []
    for token in re.findall(r"\d+(?:\.\d+)?(?:×\d+(?:\.\d+)?)?(?:mm|cm)", normalized):
        if token not in matches:
            matches.append(token)
    return matches

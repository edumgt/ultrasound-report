from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Any
import json
from Levenshtein import ratio as lev_ratio


@dataclass(frozen=True)
class Term:
    key: str
    canonical: str
    aliases: List[str]


class TermCorrector:
    def __init__(self, terms: List[Term], threshold: float = 0.86):
        self.terms = terms
        self.threshold = threshold
        self.direct: Dict[str, str] = {}
        self.key_to_canonical: Dict[str, str] = {}

        for t in terms:
            self.key_to_canonical[t.key] = t.canonical
            self.direct[t.canonical.lower()] = t.canonical
            for a in t.aliases:
                self.direct[a.lower()] = t.canonical

    @staticmethod
    def read_payload(path: str | Path) -> Dict[str, Any]:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    @staticmethod
    def from_payload(payload: Dict[str, Any]) -> Tuple['TermCorrector', Dict[str, Any]]:
        terms = [Term(key=x['key'], canonical=x['canonical'], aliases=x.get('aliases', [])) for x in payload['terms']]
        return TermCorrector(terms), payload.get('categories', {})

    @staticmethod
    def load(path: str) -> Tuple['TermCorrector', Dict[str, Any]]:
        return TermCorrector.from_payload(TermCorrector.read_payload(path))

    def correct(self, text: str) -> Tuple[str, List[Dict[str, Any]]]:
        raw = text
        lowered = raw.lower()
        changes: List[Dict[str, Any]] = []

        for alias_l, canon in sorted(self.direct.items(), key=lambda x: -len(x[0])):
            if alias_l and alias_l in lowered:
                before = raw
                raw = replace_case_insensitive(raw, alias_l, canon)
                if raw != before:
                    changes.append({'from': alias_l, 'to': canon, 'score': 1.0})
                    lowered = raw.lower()

        tokens = raw.split()
        i = 0
        while i < len(tokens):
            replaced = False
            for j in range(min(i + 3, len(tokens)), i, -1):
                cand = ' '.join(tokens[i:j])
                if len(cand) < 4:
                    continue
                cand_l = cand.lower()
                if cand_l in self.direct:
                    continue

                best_score = 0.0
                best_to = None
                for t in self.terms:
                    for a in [t.canonical] + t.aliases:
                        s = lev_ratio(cand_l, a.lower())
                        if s > best_score:
                            best_score = s
                            best_to = t.canonical

                if best_to and best_score >= self.threshold:
                    tokens[i:j] = [best_to]
                    changes.append({'from': cand, 'to': best_to, 'score': float(best_score)})
                    replaced = True
                    break
            i += 1 if not replaced else 1

        return ' '.join(tokens), changes


def replace_case_insensitive(text: str, needle_lower: str, replacement: str) -> str:
    t_low = text.lower()
    idx = t_low.find(needle_lower)
    while idx >= 0:
        text = text[:idx] + replacement + text[idx + len(needle_lower):]
        t_low = text.lower()
        idx = t_low.find(needle_lower, idx + len(replacement))
    return text

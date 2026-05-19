from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List

from core.llm_structuring import LLMStructurer
from core.measurement import normalize_measurements
from core.report_template import ReportRenderer
from core.structuring import Structurer
from core.term_correction import TermCorrector


class ReportService:
    def __init__(self, assets_dir: str | Path, term_payload: Dict[str, Any] | None = None):
        self.assets_dir = Path(assets_dir)
        payload = term_payload or TermCorrector.read_payload(self.assets_dir / 'terms.json')
        self.corrector, categories = TermCorrector.from_payload(payload)
        self.structurer = Structurer(categories, key_to_canonical=self.corrector.key_to_canonical)
        self.renderer = ReportRenderer(self.assets_dir / 'templates')
        self.llm_structurer = LLMStructurer(self.assets_dir / 'prompts')

    def correct_text(self, text: str) -> tuple[str, List[Dict[str, Any]]]:
        normalized = normalize_measurements(text.strip())
        corrected, changes = self.corrector.correct(normalized)
        return normalize_measurements(corrected), changes

    def build_report_bundle(self, text: str, template_name: str | None = None) -> Dict[str, Any]:
        corrected_text, changes = self.correct_text(text)
        rule_structured = self.structurer.extract(corrected_text)
        llm_structured = self.llm_structurer.structure(corrected_text, rule_structured)
        structured = self._merge_structured(rule_structured, llm_structured)
        report_text = self.renderer.render(structured=structured, cleaned_text=corrected_text, template_name=template_name)
        fhir_payload = self.renderer.render_fhir(structured=structured, cleaned_text=corrected_text)
        return {
            'corrected_text': corrected_text,
            'changes': changes,
            'structured': structured,
            'report_text': report_text,
            'fhir_payload': fhir_payload,
            'template_name': self.renderer.choose_template(structured, template_name),
        }

    @staticmethod
    def _merge_structured(rule_structured: Dict[str, Any], llm_structured: Dict[str, Any]) -> Dict[str, Any]:
        merged = dict(rule_structured)
        for key, value in llm_structured.items():
            if value not in (None, '', [], {}):
                merged[key] = value
        for plural_key, singular_key in (('locations', 'location'), ('lesions', 'lesion'), ('features', 'feature')):
            values = merged.get(plural_key) or ([] if merged.get(singular_key) is None else [merged[singular_key]])
            if values:
                merged[plural_key] = list(dict.fromkeys(values))
                merged[singular_key] = merged[plural_key][0]
        return merged

    @staticmethod
    def terms_to_payload(terms: Iterable[Dict[str, Any]], categories: Dict[str, Any]) -> Dict[str, Any]:
        return {'terms': list(terms), 'categories': categories}

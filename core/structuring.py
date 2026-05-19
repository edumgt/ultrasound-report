from __future__ import annotations
from typing import Any, Dict, List, Optional

from core.measurement import extract_measurements


class Structurer:
    def __init__(self, categories: Dict[str, Any], key_to_canonical: Optional[Dict[str, str]] = None):
        self.categories = categories
        self.key_to_canonical = key_to_canonical or {}

    def extract(self, corrected_text: str) -> Dict[str, Any]:
        locations = self._extract_category(corrected_text, 'location')
        lesions = self._extract_category(corrected_text, 'lesion')
        features = self._extract_category(corrected_text, 'feature')
        size_candidates = extract_measurements(corrected_text)
        domain = self._detect_domain(corrected_text)
        return {
            'location': locations[0] if locations else None,
            'lesion': lesions[0] if lesions else None,
            'feature': features[0] if features else None,
            'locations': locations,
            'lesions': lesions,
            'features': features,
            'size': size_candidates[0] if size_candidates else None,
            'measurements': size_candidates,
            'notes': 'Auto-extracted and normalized',
            'domain': domain,
            'impression': self._build_impression(domain, locations, lesions, features, size_candidates),
            'recommendation': self._build_recommendation(lesions, features, size_candidates),
        }

    def _extract_category(self, corrected_text: str, category: str) -> List[str]:
        found: List[str] = []
        for key in self.categories.get(category, []):
            canon = self.key_to_canonical.get(key, key)
            if canon in corrected_text and canon not in found:
                found.append(canon)
        return found

    def _detect_domain(self, corrected_text: str) -> str:
        domain_map = self.categories.get('domains', {})
        for domain, keys in domain_map.items():
            for key in keys:
                canon = self.key_to_canonical.get(key, key)
                if canon in corrected_text:
                    return domain
        return 'generic'

    @staticmethod
    def _build_impression(domain: str, locations: List[str], lesions: List[str], features: List[str], sizes: List[str]) -> str:
        pieces = [domain.title() if domain != 'generic' else 'Ultrasound finding']
        if lesions:
            pieces.append('/'.join(lesions))
        if locations:
            pieces.append(f'at {locations[0]}')
        if sizes:
            pieces.append(f'({sizes[0]})')
        if features:
            pieces.append(f'with {", ".join(features)} features')
        return ' '.join(pieces).strip()

    @staticmethod
    def _build_recommendation(lesions: List[str], features: List[str], sizes: List[str]) -> str:
        if lesions and ('Calcification' in features or 'Irregular Margin' in features):
            return 'Correlate with dedicated radiology review and follow-up imaging.'
        if sizes:
            return 'Track size change on follow-up ultrasound.'
        return 'Clinical correlation recommended.'

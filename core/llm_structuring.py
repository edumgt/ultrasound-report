        from __future__ import annotations

        import json
        import os
        from dataclasses import dataclass
        from pathlib import Path
        from typing import Any, Dict

        import requests


        @dataclass(frozen=True)
        class LLMConfig:
            provider: str = 'disabled'
            endpoint: str = ''
            model: str = ''
            api_key: str = ''
            timeout_seconds: int = 20

            @staticmethod
            def from_env() -> 'LLMConfig':
                provider = os.environ.get('ULTRASOUND_LLM_PROVIDER', 'disabled').strip().lower()
                if provider == 'openai_compat':
                    return LLMConfig(
                        provider=provider,
                        endpoint=os.environ.get('ULTRASOUND_LLM_ENDPOINT', 'https://api.openai.com/v1/chat/completions'),
                        model=os.environ.get('ULTRASOUND_LLM_MODEL', 'gpt-4o-mini'),
                        api_key=os.environ.get('ULTRASOUND_LLM_API_KEY', ''),
                    )
                if provider == 'ollama':
                    return LLMConfig(
                        provider=provider,
                        endpoint=os.environ.get('ULTRASOUND_LLM_ENDPOINT', 'http://127.0.0.1:11434/api/generate'),
                        model=os.environ.get('ULTRASOUND_LLM_MODEL', 'llama3.1:8b'),
                    )
                return LLMConfig()


        class LLMStructurer:
            def __init__(self, prompt_dir: str | Path, config: LLMConfig | None = None):
                self.config = config or LLMConfig.from_env()
                self.prompt_dir = Path(prompt_dir)
                self.system_prompt = self._read_prompt('ultrasound_structuring_system.txt')

            def _read_prompt(self, name: str) -> str:
                path = self.prompt_dir / name
                return path.read_text(encoding='utf-8').strip() if path.exists() else ''

            def enabled(self) -> bool:
                return self.config.provider in {'ollama', 'openai_compat'} and bool(self.config.endpoint and self.config.model)

            def structure(self, transcript: str, rule_based: Dict[str, Any]) -> Dict[str, Any]:
                if not self.enabled() or not transcript.strip():
                    return {}
                try:
                    if self.config.provider == 'ollama':
                        payload = {
                            'model': self.config.model,
                            'format': 'json',
                            'stream': False,
                            'prompt': self._build_prompt(transcript, rule_based),
                        }
                        response = requests.post(self.config.endpoint, json=payload, timeout=self.config.timeout_seconds)
                        response.raise_for_status()
                        body = response.json().get('response', '{}')
                    else:
                        payload = {
                            'model': self.config.model,
                            'response_format': {'type': 'json_object'},
                            'messages': [
                                {'role': 'system', 'content': self.system_prompt},
                                {'role': 'user', 'content': self._build_prompt(transcript, rule_based)},
                            ],
                        }
                        headers = {
                            'Authorization': f'Bearer {self.config.api_key}',
                            'Content-Type': 'application/json',
                        }
                        response = requests.post(self.config.endpoint, json=payload, headers=headers, timeout=self.config.timeout_seconds)
                        response.raise_for_status()
                        body = response.json()['choices'][0]['message']['content']
                    parsed = self._extract_json(body)
                    return parsed if isinstance(parsed, dict) else {}
                except Exception:
                    return {}

            def _build_prompt(self, transcript: str, rule_based: Dict[str, Any]) -> str:
                return (
                    f'{self.system_prompt}

'
                    'Return concise JSON only. Use the rule_based result as a hint, but correct it when needed.
'
                    f'Rule-based JSON:
{json.dumps(rule_based, ensure_ascii=False, indent=2)}

'
                    f'Transcript:
{transcript.strip()}'
                )

            @staticmethod
            def _extract_json(text: str) -> Dict[str, Any]:
                text = text.strip()
                if not text:
                    return {}
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    start = text.find('{')
                    end = text.rfind('}')
                    if start >= 0 and end > start:
                        return json.loads(text[start:end + 1])
                    raise

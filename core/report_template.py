        from __future__ import annotations

        import json
        from pathlib import Path
        from typing import Any, Dict

        from jinja2 import Environment, FileSystemLoader
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


        class ReportRenderer:
            def __init__(self, template_dir: str | Path, template_name: str = 'report_generic.j2'):
                self.template_dir = Path(template_dir)
                self.default_template_name = template_name
                self.env = Environment(loader=FileSystemLoader(str(self.template_dir)), autoescape=False, trim_blocks=True, lstrip_blocks=True)

            def choose_template(self, structured: Dict[str, Any], template_name: str | None = None) -> str:
                if template_name:
                    return template_name
                domain = structured.get('domain', 'generic')
                if domain == 'thyroid':
                    return 'report_thyroid.j2'
                if domain == 'abdomen':
                    return 'report_abdomen.j2'
                return self.default_template_name

            def render(self, structured: dict, cleaned_text: str, template_name: str | None = None) -> str:
                tpl = self.env.get_template(self.choose_template(structured, template_name))
                return tpl.render(structured=structured, cleaned_text=cleaned_text).strip()

            def render_fhir(self, structured: Dict[str, Any], cleaned_text: str) -> Dict[str, Any]:
                return {
                    'resourceType': 'DiagnosticReport',
                    'status': 'final',
                    'code': {'text': 'Ultrasound report'},
                    'conclusion': structured.get('impression') or cleaned_text,
                    'presentedForm': [
                        {'contentType': 'text/plain', 'data': cleaned_text},
                    ],
                    'result': [
                        {'text': json.dumps(structured, ensure_ascii=False)},
                    ],
                }

            def render_pdf(self, structured: Dict[str, Any], cleaned_text: str, output_path: str | Path, template_name: str | None = None) -> str:
                output_path = str(output_path)
                doc = SimpleDocTemplate(output_path, pagesize=A4)
                styles = getSampleStyleSheet()
                report_text = self.render(structured=structured, cleaned_text=cleaned_text, template_name=template_name)
                story = []
                for block in report_text.split('

'):
                    story.append(Paragraph(block.replace('
', '<br/>'), styles['BodyText']))
                    story.append(Spacer(1, 12))
                doc.build(story)
                return output_path

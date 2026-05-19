from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def export_dataset(db_path: Path, output_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        'SELECT raw_transcript, corrected_transcript, report_text, structured_json FROM recorder_recordingsession WHERE corrected_transcript <> ""'
    ).fetchall()
    dataset = [
        {
            'input': row['raw_transcript'],
            'target_transcript': row['corrected_transcript'],
            'target_report': row['report_text'],
            'structured_json': json.loads(row['structured_json']) if row['structured_json'] else {},
        }
        for row in rows
    ]
    output_path.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main() -> None:
    parser = argparse.ArgumentParser(description='Export ultrasound report fine-tuning dataset from SQLite sessions.')
    parser.add_argument('--db', default='web_django/db.sqlite3')
    parser.add_argument('--output', default='data/fine_tuning_dataset.json')
    args = parser.parse_args()
    export_dataset(Path(args.db), Path(args.output))


if __name__ == '__main__':
    main()

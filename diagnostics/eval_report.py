from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from typing import Iterable


def _ngrams(tokens: list[str], n: int) -> Counter[tuple[str, ...]]:
    return Counter(tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1))


def bleu(reference: str, prediction: str, n: int = 4) -> float:
    ref_tokens = reference.split()
    pred_tokens = prediction.split()
    if not pred_tokens:
        return 0.0
    precisions = []
    for order in range(1, n + 1):
        ref_ngrams = _ngrams(ref_tokens, order)
        pred_ngrams = _ngrams(pred_tokens, order)
        overlap = sum((pred_ngrams & ref_ngrams).values())
        total = max(sum(pred_ngrams.values()), 1)
        precisions.append(overlap / total)
    brevity_penalty = 1.0 if len(pred_tokens) > len(ref_tokens) else math.exp(1 - (len(ref_tokens) / max(len(pred_tokens), 1)))
    score = brevity_penalty * math.exp(sum(math.log(max(p, 1e-9)) for p in precisions) / n)
    return score


def rouge_l(reference: str, prediction: str) -> float:
    ref_tokens = reference.split()
    pred_tokens = prediction.split()
    dp = [[0] * (len(pred_tokens) + 1) for _ in range(len(ref_tokens) + 1)]
    for i, ref_token in enumerate(ref_tokens, start=1):
        for j, pred_token in enumerate(pred_tokens, start=1):
            if ref_token == pred_token:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    lcs = dp[-1][-1]
    precision = lcs / max(len(pred_tokens), 1)
    recall = lcs / max(len(ref_tokens), 1)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def evaluate_pairs(pairs: Iterable[dict]) -> dict:
    bleu_scores = []
    rouge_scores = []
    for pair in pairs:
        bleu_scores.append(bleu(pair['reference'], pair['prediction']))
        rouge_scores.append(rouge_l(pair['reference'], pair['prediction']))
    count = max(len(bleu_scores), 1)
    return {
        'count': len(bleu_scores),
        'bleu': sum(bleu_scores) / count,
        'rouge_l': sum(rouge_scores) / count,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description='Evaluate generated reports against gold-standard references.')
    parser.add_argument('input_file', help='JSON file with [{"reference": ..., "prediction": ...}]')
    args = parser.parse_args()
    pairs = json.loads(Path(args.input_file).read_text(encoding='utf-8'))
    print(json.dumps(evaluate_pairs(pairs), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

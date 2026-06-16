from __future__ import annotations


def compute_wer(reference: str, hypothesis: str) -> float:
    ref_words = reference.strip().split()
    hyp_words = hypothesis.strip().split()

    if not ref_words:
        return 0.0 if not hyp_words else 1.0

    rows = len(ref_words) + 1
    cols = len(hyp_words) + 1
    dp = [[0 for _ in range(cols)] for _ in range(rows)]

    for row in range(rows):
        dp[row][0] = row
    for col in range(cols):
        dp[0][col] = col

    for row in range(1, rows):
        for col in range(1, cols):
            substitution_cost = 0 if ref_words[row - 1] == hyp_words[col - 1] else 1
            dp[row][col] = min(
                dp[row - 1][col] + 1,
                dp[row][col - 1] + 1,
                dp[row - 1][col - 1] + substitution_cost,
            )

    return dp[-1][-1] / len(ref_words)

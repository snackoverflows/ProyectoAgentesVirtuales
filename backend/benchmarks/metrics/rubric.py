from __future__ import annotations


def default_llm_rubric() -> dict:
    return {
        "instruction_following": {"scale": "1-5", "weight": 0.4},
        "coherence": {"scale": "1-5", "weight": 0.6},
    }

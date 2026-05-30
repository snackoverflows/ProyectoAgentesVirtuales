from __future__ import annotations

from typing import Any, Dict, List, Tuple

from constraints_eval import evaluate_soft
from constraints_schema import (
    _aggregate_metric_value,
    _is_dict,
    _is_list,
    _normalized_metrics,
    _strip_text,
    _to_int,
)


def _objective_component(objective: Any, metrics: Dict[str, Any]) -> int:
    if not _is_dict(objective):
        return 0

    operator = _strip_text(objective.get("operator"))
    target = _strip_text(objective.get("target"))
    weight = _to_int(objective.get("weight"), 1) or 1
    aggregation = _strip_text(objective.get("aggregation")) or "sum"
    if not operator or not target:
        return 0

    if target in metrics:
        value = metrics.get(target)
    elif target == "custom":
        value = 0
    else:
        value = 0

    metric_value = _aggregate_metric_value(value, aggregation)
    if operator == "minimize":
        return -metric_value * weight
    return metric_value * weight


def schedule_rank_key(schedule: List[Dict[str, Any]], normalized: Dict[str, Any]) -> Tuple[int, ...]:
    metrics = _normalized_metrics(schedule)
    optimization = normalized.get("optimization", {}) if _is_dict(normalized.get("optimization")) else {}
    objectives = optimization.get("objectives", []) if _is_list(optimization.get("objectives")) else []

    key: List[int] = [_objective_component(objective, metrics) for objective in objectives]
    key.append(evaluate_soft(schedule, normalized, metrics=metrics))
    return tuple(key)


def rank_key_to_score(rank_key: Tuple[int, ...]) -> int:
    score = 0
    scale = 1_000_000_000
    for component in rank_key:
        score += int(component) * scale
        scale = max(1, scale // 1000)
    return int(score)

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from constraints_schema import (
    COMPARE_OPERATORS,
    ENTITY_RULE_TYPES,
    NEGATIVE_OPERATORS,
    POSITIVE_OPERATORS,
    EvaluationMetrics,
    _aggregate_metric_value,
    _block_overlaps_range,
    _block_within_range,
    _is_dict,
    _metrics_for_schedule,
    _normalize_day,
    _resolve_scoring,
    _section_id,
    _strip_text,
    _to_int,
)


def _blocks_for_rule(schedule: List[Dict[str, Any]], rule: Dict[str, Any], meeting_only: bool = False) -> List[Dict[str, Any]]:
    if rule.get("days"):
        blocks = [block for block in schedule if _normalize_day(block.get("day")) in rule.get("days", [])]
    else:
        blocks = list(schedule)
    if meeting_only and rule.get("scope") == "schedule":
        return []
    return blocks


def _entity_match_count(schedule: List[Dict[str, Any]], rule: Dict[str, Any]) -> Tuple[int, int]:
    blocks = _blocks_for_rule(schedule, rule)
    values = set(rule.get("values") or ([] if rule.get("target") is None else [rule.get("target")]))
    entity_type = rule.get("type")
    matched_sections: set = set()
    matched_days: set = set()
    matched_blocks = 0

    for block in blocks:
        day = _normalize_day(block.get("day"))
        if entity_type == "day":
            if day in (rule.get("days") or []):
                matched_days.add(day)
                matched_blocks += 1
            continue

        section_id = _section_id(block)
        block_values: List[str] = []
        if entity_type == "professor":
            block_values = [_strip_text(block.get("professor"))]
        elif entity_type == "group":
            block_values = [_strip_text(block.get("group"))]
        elif entity_type == "course":
            block_values = [_strip_text(block.get("course"))]
        elif entity_type == "campus":
            block_values = [_strip_text(block.get("campus"))]
        elif entity_type == "tag":
            block_values = [_strip_text(tag) for tag in (block.get("tags") or [])]
        elif entity_type == "time_window":
            time_range = rule.get("range") or {}
            if _block_overlaps_range(block, time_range):
                matched_blocks += 1
            continue
        else:
            continue

        if values.intersection({value for value in block_values if value}):
            matched_sections.add(section_id)

    if entity_type == "day":
        return len(matched_days), matched_blocks
    if entity_type == "time_window":
        return matched_blocks, matched_blocks
    return len(matched_sections), len(matched_sections)


def _metric_value(metrics: EvaluationMetrics, rule: Dict[str, Any]) -> int:
    target = _strip_text(rule.get("target"))
    if not target:
        return 0
    return metrics.get(target, 0)


def _compare(metric_value: int, operator: str, value: Optional[int], time_range: Optional[Dict[str, str]] = None) -> bool:
    from constraints_schema import _time_to_minutes

    if operator == "<=":
        return value is not None and metric_value <= value
    if operator == ">=":
        return value is not None and metric_value >= value
    if operator == "==":
        return value is not None and metric_value == value
    if operator == "between" and time_range:
        lower = _time_to_minutes(time_range.get("start"))
        upper = _time_to_minutes(time_range.get("end"))
        return lower <= metric_value <= upper
    if operator == "outside" and time_range:
        lower = _time_to_minutes(time_range.get("start"))
        upper = _time_to_minutes(time_range.get("end"))
        return metric_value < lower or metric_value > upper
    return False


def _rule_violated_day(rule: Dict[str, Any], blocks: List[Dict[str, Any]]) -> bool:
    operator = rule.get("operator")
    rule_days = set(rule.get("days") or [])
    schedule_days = {_normalize_day(block.get("day")) for block in blocks if _normalize_day(block.get("day"))}
    if operator in NEGATIVE_OPERATORS:
        return bool(schedule_days.intersection(rule_days))
    if operator in POSITIVE_OPERATORS:
        return not schedule_days.issubset(rule_days)
    return False


def _rule_violated_time_window(rule: Dict[str, Any], blocks: List[Dict[str, Any]]) -> bool:
    operator = rule.get("operator")
    time_range = rule.get("range") or {}
    if operator in NEGATIVE_OPERATORS:
        return any(_block_overlaps_range(block, time_range) for block in blocks)
    if operator in POSITIVE_OPERATORS:
        return any(not _block_within_range(block, time_range) for block in blocks)
    return False


def _rule_violated_entity(rule: Dict[str, Any], blocks: List[Dict[str, Any]]) -> bool:
    operator = rule.get("operator")
    matched_count, total_count = _entity_match_count(blocks, rule)
    if operator in COMPARE_OPERATORS:
        value = _to_int(rule.get("value"), None)
        return not _compare(matched_count, operator, value)
    if operator in NEGATIVE_OPERATORS:
        return matched_count > 0
    if operator in POSITIVE_OPERATORS:
        if total_count == 0:
            return False
        return matched_count != total_count
    return False


def _rule_violated_metric(rule: Dict[str, Any], metrics: EvaluationMetrics) -> bool:
    operator = rule.get("operator")
    metric_value = _aggregate_metric_value(_metric_value(metrics, rule), rule.get("aggregation", "sum"))
    if operator in COMPARE_OPERATORS:
        return not _compare(metric_value, operator, rule.get("value"))
    if operator in {"between", "outside"} and _is_dict(rule.get("range")):
        return not _compare(metric_value, operator, None, rule.get("range"))
    return False


def _rule_violated_custom(rule: Dict[str, Any], metrics: EvaluationMetrics) -> bool:
    operator = rule.get("operator")
    if operator in COMPARE_OPERATORS:
        metric_value = _aggregate_metric_value(_metric_value(metrics, rule), rule.get("aggregation", "sum"))
        return not _compare(metric_value, operator, rule.get("value"))
    return False


def _rule_violated(
    rule: Dict[str, Any],
    schedule: List[Dict[str, Any]],
    meeting_only: bool = False,
    metrics: Optional[EvaluationMetrics] = None,
) -> bool:
    blocks = _blocks_for_rule(schedule, rule, meeting_only=meeting_only)
    if meeting_only and not blocks:
        return False

    rule_type = rule.get("type")
    resolved_metrics = _metrics_for_schedule(schedule, metrics)

    if rule_type == "day":
        return _rule_violated_day(rule, blocks)
    if rule_type == "time_window":
        return _rule_violated_time_window(rule, blocks)
    if rule_type in ENTITY_RULE_TYPES:
        return _rule_violated_entity(rule, blocks)
    if rule_type == "metric":
        return _rule_violated_metric(rule, resolved_metrics)
    if rule_type == "custom":
        return _rule_violated_custom(rule, resolved_metrics)
    return False


def meeting_violates_hard(meeting: Dict[str, Any], normalized: Dict[str, Any]) -> bool:
    from constraints_schema import _normalized_metrics

    schedule = [meeting]
    metrics = _normalized_metrics(schedule)
    for rule in normalized.get("hard_rules", []):
        if rule.get("scope") == "schedule":
            continue
        if _rule_violated(rule, schedule, meeting_only=True, metrics=metrics):
            return True
    return False


def hard_violated(schedule: List[Dict[str, Any]], normalized: Dict[str, Any]) -> bool:
    from constraints_schema import _normalized_metrics

    metrics = _normalized_metrics(schedule)
    for rule in normalized.get("hard_rules", []):
        if _rule_violated(rule, schedule, metrics=metrics):
            return True
    return False


def _soft_score_day(schedule: List[Dict[str, Any]], rule: Dict[str, Any], weight: int) -> int:
    operator = rule.get("operator")
    schedule_days = {_normalize_day(block.get("day")) for block in schedule if _normalize_day(block.get("day"))}
    matched = len(schedule_days.intersection(set(rule.get("days") or [])))
    return (-weight * matched) if operator in NEGATIVE_OPERATORS else (weight * matched)


def _soft_score_time_window(schedule: List[Dict[str, Any]], rule: Dict[str, Any], weight: int) -> int:
    operator = rule.get("operator")
    blocks = _blocks_for_rule(schedule, rule)
    time_range = rule.get("range") or {}
    matched_inside = sum(1 for block in blocks if _block_within_range(block, time_range))
    matched_overlap = sum(1 for block in blocks if _block_overlaps_range(block, time_range))
    matched = matched_overlap if operator in NEGATIVE_OPERATORS else matched_inside
    return (-weight * matched) if operator in NEGATIVE_OPERATORS else (weight * matched)


def _soft_score_entity(schedule: List[Dict[str, Any]], rule: Dict[str, Any], weight: int) -> int:
    operator = rule.get("operator")
    matched_count, _ = _entity_match_count(schedule, rule)
    return (-weight * matched_count) if operator in NEGATIVE_OPERATORS else (weight * matched_count)


def _soft_score_metric_or_custom(
    rule: Dict[str, Any],
    weight: int,
    metrics: EvaluationMetrics,
    scoring_mode: str,
    scoring_per: int,
) -> int:
    operator = rule.get("operator")
    metric_value = _aggregate_metric_value(_metric_value(metrics, rule), rule.get("aggregation", "sum"))

    if scoring_mode == "linear" and operator not in COMPARE_OPERATORS:
        units = float(metric_value) / max(1, scoring_per)
        return -int(units * weight)

    satisfied = False
    if operator in COMPARE_OPERATORS:
        satisfied = _compare(metric_value, operator, rule.get("value"))
        if scoring_mode == "linear" and operator == "<=" and rule.get("value") is not None:
            excess = max(0, metric_value - int(rule.get("value")))
            return -int((excess / max(1, scoring_per)) * weight)
    elif operator in {"between", "outside"} and _is_dict(rule.get("range")):
        satisfied = _compare(metric_value, operator, None, rule.get("range"))
    elif operator in {"prefer", "include"}:
        satisfied = metric_value > 0
    elif operator in NEGATIVE_OPERATORS:
        satisfied = metric_value == 0

    if satisfied:
        return weight
    if operator in NEGATIVE_OPERATORS:
        return -weight
    return -weight


def evaluate_soft(
    schedule: List[Dict[str, Any]],
    normalized: Dict[str, Any],
    metrics: Optional[EvaluationMetrics] = None,
) -> int:
    total = 0
    resolved_metrics = _metrics_for_schedule(schedule, metrics)

    for rule in normalized.get("soft_rules", []):
        rule_type = rule.get("type")
        weight = _to_int(rule.get("weight"), 1) or 1
        scoring = _resolve_scoring(rule, normalized)
        scoring_mode = scoring.get("mode", "fixed")
        scoring_per = _to_int(scoring.get("per"), 30) or 30

        if rule_type == "day":
            total += _soft_score_day(schedule, rule, weight)
            continue
        if rule_type == "time_window":
            total += _soft_score_time_window(schedule, rule, weight)
            continue
        if rule_type in ENTITY_RULE_TYPES:
            total += _soft_score_entity(schedule, rule, weight)
            continue
        if rule_type in {"metric", "custom"}:
            total += _soft_score_metric_or_custom(rule, weight, resolved_metrics, scoring_mode, scoring_per)

    return int(total)

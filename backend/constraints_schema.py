from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple


DAYS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
DAY_ALIASES = {
    "lunes": "Lunes",
    "martes": "Martes",
    "miercoles": "Miércoles",
    "miércoles": "Miércoles",
    "jueves": "Jueves",
    "viernes": "Viernes",
    "sabado": "Sábado",
    "sábado": "Sábado",
    "domingo": "Domingo",
}

ALLOWED_TYPES = {"day", "time_window", "professor", "group", "course", "metric", "tag", "campus", "custom"}
ALLOWED_SCOPES = {"meeting", "course", "schedule", "day"}
ALLOWED_OPERATORS = {"include", "exclude", "prefer", "avoid", "<=", ">=", "==", "between", "outside"}
POSITIVE_OPERATORS = {"include", "prefer", "between", "<=", ">=", "=="}
NEGATIVE_OPERATORS = {"exclude", "avoid", "outside"}
COMPARE_OPERATORS = {"<=", ">=", "=="}
DEFAULT_SCOPE_BY_TYPE = {
    "day": "day",
    "time_window": "meeting",
    "professor": "course",
    "group": "course",
    "course": "course",
    "metric": "schedule",
    "tag": "schedule",
    "campus": "schedule",
    "custom": "schedule",
}

KNOWN_METRICS = {
    "distinct_courses",
    "days_on_campus",
    "total_gap_minutes",
    "morning_classes",
    "selected_sections",
    "courses_per_day",
    "meetings_per_day",
    "gaps_by_day",
}

METRIC_TARGET_ALIASES = {
    "course_count": "distinct_courses",
    "courses": "distinct_courses",
    "days": "days_on_campus",
    "days_count": "days_on_campus",
    "dias": "days_on_campus",
    "day_count": "days_on_campus",
    "gaps": "total_gap_minutes",
    "morning": "morning_classes",
    "sections": "selected_sections",
}

SUPPORTED_SCORING_MODES = {"fixed", "linear"}
SUPPORTED_AGGREGATIONS = {"sum", "max", "min", "count"}
SUPPORTED_OBJECTIVE_OPERATORS = {"maximize", "minimize"}
ENTITY_RULE_TYPES = {"professor", "group", "course", "campus", "tag"}
EvaluationMetrics = Dict[str, Any]


def _is_dict(value: Any) -> bool:
    return isinstance(value, dict)


def _is_list(value: Any) -> bool:
    return isinstance(value, list)


def _strip_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _to_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_day(value: Any) -> Optional[str]:
    label = _strip_text(value)
    if not label:
        return None
    return DAY_ALIASES.get(label.casefold(), label if label in DAYS else None)


def _normalize_days(value: Any) -> List[str]:
    if not _is_list(value):
        return []
    days: List[str] = []
    for item in value:
        normalized = _normalize_day(item)
        if normalized and normalized not in days:
            days.append(normalized)
    return days


def _normalize_time(value: Any) -> Optional[str]:
    label = _strip_text(value)
    if not label or ":" not in label:
        return None
    try:
        hours_text, minutes_text = label.split(":", 1)
        hours = int(hours_text)
        minutes = int(minutes_text)
    except ValueError:
        return None
    if hours < 0 or hours > 23 or minutes < 0 or minutes > 59:
        return None
    return f"{hours:02d}:{minutes:02d}"


def _time_to_minutes(time_value: Any) -> int:
    normalized = _normalize_time(time_value)
    if normalized is None:
        raise ValueError(f"Invalid time value: {time_value!r}")
    hours_text, minutes_text = normalized.split(":", 1)
    return int(hours_text) * 60 + int(minutes_text)


def _normalize_range(value: Any) -> Tuple[Dict[str, str], List[str]]:
    errors: List[str] = []
    if not _is_dict(value):
        return {}, ["range must be an object with start and end."]

    start = _normalize_time(value.get("start"))
    end = _normalize_time(value.get("end"))
    if not start or not end:
        errors.append("range requires valid HH:mm start and end values.")
        return {}, errors

    if _time_to_minutes(start) >= _time_to_minutes(end):
        errors.append("range start must be earlier than range end.")
        return {}, errors

    return {"start": start, "end": end}, errors


def _normalize_values(value: Any) -> List[str]:
    if not _is_list(value):
        return []
    values: List[str] = []
    for item in value:
        text = _strip_text(item)
        if text and text not in values:
            values.append(text)
    return values


def _infer_scope(rule_type: str) -> str:
    return DEFAULT_SCOPE_BY_TYPE.get(rule_type, "schedule")


def _canonical_metric_target(value: Any) -> str:
    target = _strip_text(value)
    if not target:
        return ""
    return METRIC_TARGET_ALIASES.get(target.casefold(), target)


def _normalize_scoring_config(value: Any) -> Tuple[Dict[str, Any], List[str]]:
    errors: List[str] = []
    normalized = {"mode": "fixed", "per": 30}
    if value is None:
        return normalized, errors
    if not _is_dict(value):
        return normalized, ["scoring must be an object."]

    mode = _strip_text(value.get("mode")) or "fixed"
    if mode not in SUPPORTED_SCORING_MODES:
        errors.append(f"Unsupported scoring mode: {value.get('mode')!r}.")
        mode = "fixed"

    per = _to_int(value.get("per"), 30)
    if per is None or per <= 0:
        errors.append("scoring.per must be a positive integer.")
        per = 30

    normalized["mode"] = mode
    normalized["per"] = per
    return normalized, errors


def _resolve_scoring(rule: Dict[str, Any], normalized: Dict[str, Any]) -> Dict[str, Any]:
    if _is_dict(rule.get("scoring")):
        return rule["scoring"]
    scoring = normalized.get("scoring")
    if _is_dict(scoring):
        return scoring
    return {"mode": "fixed", "per": 30}


def _aggregate_metric_value(value: Any, aggregation: str) -> int:
    aggregation = aggregation if aggregation in SUPPORTED_AGGREGATIONS else "sum"

    if isinstance(value, dict):
        numeric_values = [int(item) for item in value.values() if isinstance(item, (int, float))]
        if aggregation == "count":
            return len(value)
        if not numeric_values:
            return 0
        if aggregation == "max":
            return max(numeric_values)
        if aggregation == "min":
            return min(numeric_values)
        return sum(numeric_values)

    if isinstance(value, list):
        if aggregation == "count":
            return len(value)
        numeric_values = [int(item) for item in value if isinstance(item, (int, float))]
        if not numeric_values:
            return len(value) if aggregation == "count" else 0
        if aggregation == "max":
            return max(numeric_values)
        if aggregation == "min":
            return min(numeric_values)
        return sum(numeric_values)

    if aggregation == "count":
        return 1 if value not in (None, "") else 0

    if isinstance(value, (int, float)):
        return int(value)

    return 0


def _block_within_range(block: Dict[str, Any], time_range: Dict[str, str]) -> bool:
    start = _time_to_minutes(block.get("start"))
    end = _time_to_minutes(block.get("end"))
    range_start = _time_to_minutes(time_range.get("start"))
    range_end = _time_to_minutes(time_range.get("end"))
    return start >= range_start and end <= range_end


def _block_overlaps_range(block: Dict[str, Any], time_range: Dict[str, str]) -> bool:
    start = _time_to_minutes(block.get("start"))
    end = _time_to_minutes(block.get("end"))
    range_start = _time_to_minutes(time_range.get("start"))
    range_end = _time_to_minutes(time_range.get("end"))
    return start < range_end and end > range_start


def _section_id(block: Dict[str, Any]) -> str:
    return _strip_text(block.get("section_id")) or f"{_strip_text(block.get('course'))}|{_strip_text(block.get('group'))}"


def _normalized_metrics(schedule: List[Dict[str, Any]]) -> Dict[str, Any]:
    blocks_by_day: Dict[str, List[Dict[str, Any]]] = {}
    distinct_days: List[str] = []
    distinct_courses: List[str] = []
    sections: List[str] = []
    tags_by_schedule: Dict[str, set] = {}
    morning_classes = 0

    for block in schedule:
        day = _strip_text(block.get("day"))
        course = _strip_text(block.get("course"))
        section_id = _section_id(block)
        if day:
            blocks_by_day.setdefault(day, []).append(block)
            if day not in distinct_days:
                distinct_days.append(day)
        if course and course not in distinct_courses:
            distinct_courses.append(course)
        if section_id and section_id not in sections:
            sections.append(section_id)
        if _time_to_minutes(block.get("start")) < 12 * 60:
            morning_classes += 1
        for tag in block.get("tags") or []:
            tag_text = _strip_text(tag)
            if tag_text:
                tags_by_schedule.setdefault(tag_text, set()).add(section_id)

    total_gap_minutes = 0
    gaps_by_day: Dict[str, int] = {}
    meetings_per_day: Dict[str, int] = {}
    courses_per_day: Dict[str, int] = {}
    for day, blocks in blocks_by_day.items():
        meetings_per_day[day] = len(blocks)
        courses_per_day[day] = len({block.get("course") for block in blocks if _strip_text(block.get("course"))})
        sorted_blocks = sorted(blocks, key=lambda block: _time_to_minutes(block.get("start")))
        day_gap = 0
        for left_block, right_block in zip(sorted_blocks, sorted_blocks[1:]):
            gap = _time_to_minutes(right_block.get("start")) - _time_to_minutes(left_block.get("end"))
            if gap > 0:
                day_gap += gap
        gaps_by_day[day] = day_gap
        total_gap_minutes += day_gap

    return {
        "distinct_courses": len(distinct_courses),
        "days_on_campus": len(distinct_days),
        "total_gap_minutes": total_gap_minutes,
        "morning_classes": morning_classes,
        "selected_sections": len(sections),
        "meetings_per_day": meetings_per_day,
        "courses_per_day": courses_per_day,
        "gaps_by_day": gaps_by_day,
        "blocks_by_day": blocks_by_day,
        "tags_by_schedule": {tag: len(section_ids) for tag, section_ids in tags_by_schedule.items()},
    }


def _metrics_for_schedule(schedule: List[Dict[str, Any]], metrics: Optional[EvaluationMetrics] = None) -> EvaluationMetrics:
    return metrics if isinstance(metrics, dict) else _normalized_metrics(schedule)


def _normalize_objective(item: Any) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    errors: List[str] = []
    if not _is_dict(item):
        return None, ["optimization objective must be an object with operator/target/priority."]

    operator = _strip_text(item.get("operator")) or "maximize"
    if operator == "min":
        operator = "minimize"
    elif operator == "max":
        operator = "maximize"

    target = _canonical_metric_target(item.get("target"))
    if not target:
        errors.append("optimization objective requires a target.")
    if operator not in SUPPORTED_OBJECTIVE_OPERATORS:
        errors.append(f"Unsupported optimization operator: {item.get('operator')!r}. Use 'maximize' or 'minimize'.")

    priority = _to_int(item.get("priority"), None)
    if priority is None:
        errors.append("optimization objective requires an integer 'priority'.")
    weight = _to_int(item.get("weight"), 1) or 1
    reason = _strip_text(item.get("reason"))
    aggregation = _strip_text(item.get("aggregation")) or "sum"

    if target and target not in KNOWN_METRICS and target != "custom":
        errors.append(f"Unknown optimization target: {target!r}.")
    if aggregation not in SUPPORTED_AGGREGATIONS:
        errors.append(f"Unsupported aggregation: {item.get('aggregation')!r}.")
        aggregation = "sum"

    normalized = {"operator": operator, "target": target, "weight": weight, "reason": reason, "priority": priority, "aggregation": aggregation}
    return normalized, errors


def _ensure_primary_distinct_courses_objective(objectives: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    has_distinct_courses = any(
        _is_dict(item)
        and _strip_text(item.get("target")) == "distinct_courses"
        and _strip_text(item.get("operator")) == "maximize"
        for item in objectives
    )
    if has_distinct_courses:
        return objectives

    shifted: List[Dict[str, Any]] = []
    for item in objectives:
        if not _is_dict(item):
            continue
        updated = dict(item)
        updated["priority"] = int(_to_int(updated.get("priority"), 9999) or 9999) + 1
        shifted.append(updated)

    primary = {
        "operator": "maximize",
        "target": "distinct_courses",
        "priority": 1,
        "weight": 1,
        "aggregation": "sum",
        "reason": "Base objective: maximize distinct courses",
    }
    return [primary] + shifted


def validate_rule(rule: Any, kind: str = "hard") -> Tuple[Optional[Dict[str, Any]], List[str]]:
    errors: List[str] = []
    if not _is_dict(rule):
        return None, [f"{kind} rule must be an object."]

    rule_type = _strip_text(rule.get("type"))
    if rule_type not in ALLOWED_TYPES:
        errors.append(f"Unsupported rule type: {rule.get('type')!r}")

    scope = _strip_text(rule.get("scope")) or _infer_scope(rule_type)
    if scope not in ALLOWED_SCOPES:
        errors.append(f"Unsupported scope: {rule.get('scope')!r}")

    operator = _strip_text(rule.get("operator"))
    if operator not in ALLOWED_OPERATORS:
        errors.append(f"Unsupported operator: {rule.get('operator')!r}")

    days = _normalize_days(rule.get("days"))
    values = _normalize_values(rule.get("values"))
    target = _canonical_metric_target(rule.get("target")) or None

    time_range: Dict[str, str] = {}
    range_errors: List[str] = []
    if _is_dict(rule.get("range")):
        time_range, range_errors = _normalize_range(rule.get("range"))
        errors.extend(range_errors)

    value = _to_int(rule.get("value"), None)
    weight = _to_int(rule.get("weight"), 1)
    reason = _strip_text(rule.get("reason"))
    aggregation = _strip_text(rule.get("aggregation")) or "sum"
    scoring_value = rule.get("scoring")
    scoring: Optional[Dict[str, Any]] = None
    if scoring_value is not None:
        scoring, scoring_errors = _normalize_scoring_config(scoring_value)
        errors.extend(scoring_errors)

    if kind == "soft" and (weight is None or weight <= 0):
        errors.append("Soft rules require a positive integer weight.")

    if rule_type == "day":
        if not days:
            errors.append("Day rules require a non-empty days list.")
    elif rule_type == "time_window":
        if not time_range:
            errors.append("time_window rules require a valid range.")
    elif rule_type in {"professor", "group", "course", "campus"}:
        if not values:
            errors.append(f"{rule_type} rules require at least one value.")
    elif rule_type == "tag":
        if not target and not values:
            errors.append("tag rules require a target or values.")
    elif rule_type == "metric":
        if not target:
            errors.append("metric rules require a target.")
        if target and target not in KNOWN_METRICS and target != "custom":
            errors.append(f"Unknown metric target: {target!r}.")
        if operator in COMPARE_OPERATORS and value is None:
            errors.append("metric rules using comparison operators require a numeric value.")
        if aggregation not in SUPPORTED_AGGREGATIONS:
            errors.append(f"Unsupported aggregation: {rule.get('aggregation')!r}.")
            aggregation = "sum"
    elif rule_type == "custom":
        if not any([days, values, target, time_range, value is not None]):
            errors.append("custom rules require at least one structured field.")
        if aggregation not in SUPPORTED_AGGREGATIONS:
            errors.append(f"Unsupported aggregation: {rule.get('aggregation')!r}.")
            aggregation = "sum"

    normalized = {
        "type": rule_type,
        "scope": scope,
        "operator": operator,
        "days": days,
        "values": values,
        "range": time_range,
        "target": target,
        "value": value,
        "weight": weight if weight is not None else 1,
        "reason": reason,
        "aggregation": aggregation,
        "scoring": scoring,
        "raw": rule,
    }
    return normalized, errors


def validate_constraints(raw: Any) -> List[str]:
    normalized = normalize_constraints(raw)
    return list(normalized.get("validation_errors", []))


def canonicalize_constraints_payload(raw: Any) -> Any:
    if not _is_dict(raw):
        return raw

    payload = deepcopy(raw)

    for rule_group in ("hard", "soft"):
        rules = payload.get(rule_group)
        if not _is_list(rules):
            continue
        for rule in rules:
            if not _is_dict(rule):
                continue
            if rule.get("type") == "metric" and "target" in rule:
                canonical_target = _canonical_metric_target(rule.get("target"))
                if canonical_target:
                    rule["target"] = canonical_target
            if rule.get("type") == "day" and _is_list(rule.get("days")):
                normalized_days = _normalize_days(rule.get("days"))
                if normalized_days:
                    rule["days"] = normalized_days

    optimization = payload.get("optimization")
    if _is_dict(optimization):
        objectives = optimization.get("objectives")
        if _is_list(objectives):
            for objective in objectives:
                if not _is_dict(objective):
                    continue
                operator = _strip_text(objective.get("operator"))
                if operator == "min":
                    objective["operator"] = "minimize"
                elif operator == "max":
                    objective["operator"] = "maximize"

                if "target" in objective:
                    canonical_target = _canonical_metric_target(objective.get("target"))
                    if canonical_target:
                        objective["target"] = canonical_target

                priority = _to_int(objective.get("priority"), None)
                if priority is not None:
                    objective["priority"] = priority

    return payload


def normalize_constraints(raw: Dict[str, Any]) -> Dict[str, Any]:
    normalized = {
        "hard_rules": [],
        "soft_rules": [],
        "optimization": {"objectives": []},
        "scoring": {"mode": "fixed", "per": 30},
        "validation_errors": [],
    }

    if not _is_dict(raw):
        normalized["validation_errors"].append("Constraints payload must be an object.")
        return normalized

    hard_rules = raw.get("hard", [])
    if hard_rules is None:
        hard_rules = []
    if not _is_list(hard_rules):
        normalized["validation_errors"].append("hard must be an array of rules.")
        hard_rules = []

    soft_rules = raw.get("soft", [])
    if soft_rules is None:
        soft_rules = []
    if not _is_list(soft_rules):
        normalized["validation_errors"].append("soft must be an array of rules.")
        soft_rules = []

    for index, rule in enumerate(hard_rules):
        validated, errors = validate_rule(rule, "hard")
        if errors:
            normalized["validation_errors"].extend([f"hard[{index}]: {error}" for error in errors])
            continue
        if validated is not None:
            normalized["hard_rules"].append(validated)

    for index, rule in enumerate(soft_rules):
        validated, errors = validate_rule(rule, "soft")
        if errors:
            normalized["validation_errors"].extend([f"soft[{index}]: {error}" for error in errors])
            continue
        if validated is not None:
            normalized["soft_rules"].append(validated)

    known_keys = {"hard", "soft", "optimization", "scoring"}
    for key in raw.keys():
        if key not in known_keys:
            normalized["validation_errors"].append(f"Unsupported top-level key: {key!r}. Use only 'hard', 'soft', 'optimization' and 'scoring'.")

    optimization = raw.get("optimization", {})
    if not _is_dict(optimization):
        normalized["validation_errors"].append("optimization must be an object.")
    else:
        allowed_optimization_keys = {"objectives"}
        for key in optimization.keys():
            if key not in allowed_optimization_keys:
                normalized["validation_errors"].append(f"Unsupported optimization key: {key!r}. Use only 'objectives'.")

        objectives = optimization.get("objectives", [])
        if objectives is None:
            objectives = []
        if not _is_list(objectives):
            normalized["validation_errors"].append("optimization.objectives must be an array.")
            objectives = []

        parsed: List[Dict[str, Any]] = []
        for index, item in enumerate(objectives):
            objective, errors = _normalize_objective(item)
            if errors:
                normalized["validation_errors"].extend([f"optimization.objectives[{index}]: {error}" for error in errors])
                continue
            if objective is not None:
                parsed.append(objective)

        parsed_with_primary = _ensure_primary_distinct_courses_objective(parsed)
        parsed_sorted = sorted(parsed_with_primary, key=lambda o: int(o.get("priority", 9999)))
        normalized["optimization"]["objectives"] = parsed_sorted

    scoring_value = raw.get("scoring")
    scoring, scoring_errors = _normalize_scoring_config(scoring_value)
    if scoring_value is not None:
        normalized["validation_errors"].extend(scoring_errors)
    normalized["scoring"] = scoring

    return normalized

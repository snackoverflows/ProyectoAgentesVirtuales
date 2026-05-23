from __future__ import annotations

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

SUPPORTED_SCORING_MODES = {"fixed", "linear"}
SUPPORTED_AGGREGATIONS = {"sum", "max", "min", "count"}


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


def _time_to_minutes(time_value: Any) -> int:
    normalized = _normalize_time(time_value)
    if normalized is None:
        raise ValueError(f"Invalid time value: {time_value!r}")
    hours_text, minutes_text = normalized.split(":", 1)
    return int(hours_text) * 60 + int(minutes_text)


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


def _section_key(block: Dict[str, Any]) -> Tuple[str, str]:
    return _section_id(block), _strip_text(block.get("course"))


def _normalized_metrics(schedule: List[Dict[str, Any]]) -> Dict[str, Any]:
    blocks_by_day: Dict[str, List[Dict[str, Any]]] = {}
    distinct_days: List[str] = []
    distinct_courses: List[str] = []
    sections: List[str] = []
    tags_by_schedule: Dict[str, set] = {}
    tags_by_section: Dict[str, set] = {}
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
                tags_by_section.setdefault(section_id, set()).add(tag_text)

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


def _normalize_objective(item: Any) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    errors: List[str] = []
    # New canonical objective format: require an object with operator, target, priority, weight
    if not _is_dict(item):
        return None, ["optimization objective must be an object with operator/target/priority."]

    operator = _strip_text(item.get("operator")) or "maximize"
    target = _strip_text(item.get("target"))
    if not target:
        errors.append("optimization objective requires a target.")
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
    target = _strip_text(rule.get("target")) or None

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
    # Reject unexpected top-level keys in favor of canonical `hard`/`soft`/`optimization`/`scoring`.
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
                normalized["validation_errors"].append(
                    f"Unsupported optimization key: {key!r}. Use only 'objectives'."
                )

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

        # sort by priority ascending (1 highest)
        parsed_sorted = sorted(parsed, key=lambda o: int(o.get("priority", 9999)))
        if not parsed_sorted:
            parsed_sorted = [
                {
                    "operator": "maximize",
                    "target": "distinct_courses",
                    "priority": 1,
                    "weight": 1,
                    "aggregation": "sum",
                }
            ]
        normalized["optimization"]["objectives"] = parsed_sorted

    scoring_value = raw.get("scoring")
    scoring, scoring_errors = _normalize_scoring_config(scoring_value)
    if scoring_value is not None:
        normalized["validation_errors"].extend(scoring_errors)
    normalized["scoring"] = scoring

    return normalized


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


def _metric_value(schedule: List[Dict[str, Any]], metrics: Dict[str, Any], rule: Dict[str, Any]) -> int:
    target = _strip_text(rule.get("target"))
    if not target:
        return 0
    return metrics.get(target, 0)


def _compare(metric_value: int, operator: str, value: Optional[int], time_range: Optional[Dict[str, str]] = None) -> bool:
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


def _rule_violated(rule: Dict[str, Any], schedule: List[Dict[str, Any]], meeting_only: bool = False) -> bool:
    blocks = _blocks_for_rule(schedule, rule, meeting_only=meeting_only)
    if meeting_only and not blocks:
        return False

    rule_type = rule.get("type")
    operator = rule.get("operator")

    if rule_type == "day":
        rule_days = set(rule.get("days") or [])
        schedule_days = {_normalize_day(block.get("day")) for block in blocks if _normalize_day(block.get("day"))}
        if operator in NEGATIVE_OPERATORS:
            return bool(schedule_days.intersection(rule_days))
        if operator in POSITIVE_OPERATORS:
            return not schedule_days.issubset(rule_days)
        return False

    if rule_type == "time_window":
        time_range = rule.get("range") or {}
        if operator in NEGATIVE_OPERATORS:
            # negative semantics: any overlap with the forbidden range is a violation
            return any(_block_overlaps_range(block, time_range) for block in blocks)
        if operator in POSITIVE_OPERATORS:
            # positive semantics: expect blocks to be fully within the range
            return any(not _block_within_range(block, time_range) for block in blocks)
        return False

    if rule_type in {"professor", "group", "course", "campus", "tag"}:
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

    if rule_type == "metric":
        metrics = _normalized_metrics(schedule)
        metric_value = _aggregate_metric_value(_metric_value(schedule, metrics, rule), rule.get("aggregation", "sum"))
        if operator in COMPARE_OPERATORS:
            return not _compare(metric_value, operator, rule.get("value"))
        if operator in {"between", "outside"} and _is_dict(rule.get("range")):
            return not _compare(metric_value, operator, None, rule.get("range"))
        return False

    if rule_type == "custom":
        if operator in COMPARE_OPERATORS:
            metrics = _normalized_metrics(schedule)
            metric_value = _aggregate_metric_value(_metric_value(schedule, metrics, rule), rule.get("aggregation", "sum"))
            return not _compare(metric_value, operator, rule.get("value"))
        return False

    return False


def meeting_violates_hard(meeting: Dict[str, Any], normalized: Dict[str, Any]) -> bool:
    schedule = [meeting]
    for rule in normalized.get("hard_rules", []):
        # only evaluate meeting-scoped rules here
        if rule.get("scope") == "schedule":
            continue
        if _rule_violated(rule, schedule, meeting_only=True):
            return True
    return False


def hard_violated(schedule: List[Dict[str, Any]], normalized: Dict[str, Any]) -> bool:
    for rule in normalized.get("hard_rules", []):
        if _rule_violated(rule, schedule):
            return True
    return False


def evaluate_soft(schedule: List[Dict[str, Any]], normalized: Dict[str, Any]) -> int:
    total = 0
    metrics = _normalized_metrics(schedule)

    for rule in normalized.get("soft_rules", []):
        operator = rule.get("operator")
        rule_type = rule.get("type")
        weight = _to_int(rule.get("weight"), 1) or 1
        scoring = _resolve_scoring(rule, normalized)
        scoring_mode = scoring.get("mode", "fixed")
        scoring_per = _to_int(scoring.get("per"), 30) or 30

        if rule_type == "day":
            schedule_days = {_normalize_day(block.get("day")) for block in schedule if _normalize_day(block.get("day"))}
            matched = len(schedule_days.intersection(set(rule.get("days") or [])))
            if operator in NEGATIVE_OPERATORS:
                total -= weight * matched
            else:
                total += weight * matched
            continue

        if rule_type == "time_window":
            blocks = _blocks_for_rule(schedule, rule)
            time_range = rule.get("range") or {}
            matched_inside = sum(1 for block in blocks if _block_within_range(block, time_range))
            matched_overlap = sum(1 for block in blocks if _block_overlaps_range(block, time_range))
            matched = matched_overlap if operator in NEGATIVE_OPERATORS else matched_inside
            if operator in NEGATIVE_OPERATORS:
                total -= weight * matched
            else:
                total += weight * matched
            continue

        if rule_type in {"professor", "group", "course", "campus", "tag"}:
            matched_count, _ = _entity_match_count(schedule, rule)
            if operator in NEGATIVE_OPERATORS:
                total -= weight * matched_count
            else:
                total += weight * matched_count
            continue

        if rule_type in {"metric", "custom"}:
            metric_value = _aggregate_metric_value(_metric_value(schedule, metrics, rule), rule.get("aggregation", "sum"))
            if scoring_mode == "linear" and operator not in COMPARE_OPERATORS:
                units = float(metric_value) / max(1, scoring_per)
                total -= int(units * weight)
                continue

            satisfied = False
            if operator in COMPARE_OPERATORS:
                satisfied = _compare(metric_value, operator, rule.get("value"))
                # for linear with threshold, penalize excess proportionally
                if scoring_mode == "linear" and operator == "<=" and rule.get("value") is not None:
                    excess = max(0, metric_value - int(rule.get("value")))
                    total -= int((excess / max(1, scoring_per)) * weight)
                    continue
            elif operator in {"between", "outside"} and _is_dict(rule.get("range")):
                satisfied = _compare(metric_value, operator, None, rule.get("range"))
            elif operator in {"prefer", "include"}:
                satisfied = metric_value > 0
            elif operator in NEGATIVE_OPERATORS:
                satisfied = metric_value == 0

            if satisfied:
                total += weight
            elif operator in NEGATIVE_OPERATORS:
                total -= weight
            else:
                total -= weight

    return int(total)


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
    key.append(evaluate_soft(schedule, normalized))
    return tuple(key)


def rank_key_to_score(rank_key: Tuple[int, ...]) -> int:
    score = 0
    scale = 1_000_000_000
    for component in rank_key:
        score += int(component) * scale
        scale = max(1, scale // 1000)
    return int(score)

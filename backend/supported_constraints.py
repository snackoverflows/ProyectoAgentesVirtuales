from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List

from constraints_schema import canonicalize_constraints_payload


def _normalize_text(value: Any) -> str:
    text = str(value or "").strip().casefold()
    replacements = {
        "á": "a",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
        "ü": "u",
        "ñ": "n",
    }
    for original, replacement in replacements.items():
        text = text.replace(original, replacement)
    return " ".join(text.split())


SUPPORTED_CONSTRAINTS: List[Dict[str, Any]] = [
    {
        "id": "few_days_on_campus",
        "phrases": [
            "quiero ir pocos dias a la u",
            "quiero ir pocos dias",
            "ir pocos dias a la u",
            "ir pocos dias",
            "priorizar pocos dias",
            "pocos dias en la u",
            "pocos dias en la universidad",
            "menos dias en la u",
            "menos dias en la universidad",
            "la menor cantidad de dias posible",
        ],
        "constraints": {
            "hard": [],
            "soft": [],
            "optimization": {
                "objectives": [
                    {
                        "operator": "minimize",
                        "target": "days_on_campus",
                        "priority": 2,
                        "weight": 1,
                        "aggregation": "sum",
                        "reason": "Ir pocos dias a la universidad",
                    }
                ]
            },
            "scoring": {"mode": "fixed", "per": 30},
        },
    },
    {
        "id": "morning_only",
        "phrases": [
            "quiero solo clases en la manana",
            "solo clases en la manana",
            "solo en la manana",
            "solo manana",
            "solo mananas",
            "quiero clases solo en la manana",
            "quiero solo clases por la manana",
            "quiero clases solo por la manana",
            "quiero todas las clases en la manana",
            "todas las clases en la manana",
            "sin tardes",
            "sin la tarde",
            "evitar clases en la tarde",
            "evitar la tarde",
            "no en la tarde",
            "no por la tarde",
            "no quiero clases en la tarde",
            "no quiero ir en la tarde",
        ],
        "constraints": {
            "hard": [
                {
                    "type": "time_window",
                    "scope": "meeting",
                    "operator": "outside",
                    "range": {"start": "12:00", "end": "23:59"},
                    "reason": "Solo clases en la manana",
                }
            ],
            "soft": [],
            "optimization": {"objectives": []},
            "scoring": {"mode": "fixed", "per": 30},
        },
    },
]


def _ensure_constraints_shape(constraints: Any) -> Dict[str, Any]:
    if not isinstance(constraints, dict):
        constraints = {}

    ensured = deepcopy(constraints)
    if not isinstance(ensured.get("hard"), list):
        ensured["hard"] = []
    if not isinstance(ensured.get("soft"), list):
        ensured["soft"] = []
    optimization = ensured.get("optimization")
    if not isinstance(optimization, dict):
        optimization = {}
        ensured["optimization"] = optimization
    if not isinstance(optimization.get("objectives"), list):
        optimization["objectives"] = []
    if not isinstance(ensured.get("scoring"), dict):
        ensured["scoring"] = {"mode": "fixed", "per": 30}
    return canonicalize_constraints_payload(ensured)


def _matches_supported_constraint(user_text: str, phrases: List[str]) -> bool:
    normalized_text = _normalize_text(user_text)
    return any(phrase in normalized_text for phrase in phrases)


def _same_time_window_rule(left: Dict[str, Any], right: Dict[str, Any]) -> bool:
    left_range = left.get("range") or {}
    right_range = right.get("range") or {}
    return (
        left.get("type") == right.get("type")
        and left.get("scope") == right.get("scope")
        and left.get("operator") == right.get("operator")
        and left_range.get("start") == right_range.get("start")
        and left_range.get("end") == right_range.get("end")
    )


def _merge_hard_rules(base_rules: List[Dict[str, Any]], incoming_rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged = [deepcopy(rule) for rule in base_rules if isinstance(rule, dict)]
    for incoming in incoming_rules:
        if not isinstance(incoming, dict):
            continue

        replaced = False
        for index, current in enumerate(merged):
            if _same_time_window_rule(current, incoming):
                updated = deepcopy(incoming)
                if current.get("reason") and not updated.get("reason"):
                    updated["reason"] = current.get("reason")
                merged[index] = updated
                replaced = True
                break

        if not replaced:
            merged.append(deepcopy(incoming))
    return merged


def _same_objective(left: Dict[str, Any], right: Dict[str, Any]) -> bool:
    return (
        left.get("operator") == right.get("operator")
        and left.get("target") == right.get("target")
        and left.get("aggregation", "sum") == right.get("aggregation", "sum")
    )


def _merge_objectives(base_objectives: List[Dict[str, Any]], incoming_objectives: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged = [deepcopy(item) for item in base_objectives if isinstance(item, dict)]
    for incoming in incoming_objectives:
        if not isinstance(incoming, dict):
            continue

        replaced = False
        for index, current in enumerate(merged):
            if _same_objective(current, incoming):
                updated = deepcopy(current)
                updated.update(deepcopy(incoming))
                merged[index] = updated
                replaced = True
                break

        if not replaced:
            merged.append(deepcopy(incoming))

    merged.sort(key=lambda item: int(item.get("priority", 9999)))
    return merged


def merge_supported_constraints(current_constraints: Any, extra_constraints: Any) -> Dict[str, Any]:
    merged = _ensure_constraints_shape(current_constraints)
    incoming = _ensure_constraints_shape(extra_constraints)

    merged["hard"] = _merge_hard_rules(merged.get("hard", []), incoming.get("hard", []))
    merged["optimization"]["objectives"] = _merge_objectives(
        (merged.get("optimization") or {}).get("objectives", []),
        (incoming.get("optimization") or {}).get("objectives", []),
    )

    return canonicalize_constraints_payload(merged)


def interpret_supported_constraints(user_text: str, current_constraints: Any) -> Dict[str, Any]:
    matched_entries = [
        entry
        for entry in SUPPORTED_CONSTRAINTS
        if _matches_supported_constraint(user_text, entry.get("phrases", []))
    ]

    merged_constraints = _ensure_constraints_shape(current_constraints)
    applied_ids: List[str] = []
    detected_ids: List[str] = []

    for entry in matched_entries:
        entry_id = entry.get("id")
        if isinstance(entry_id, str):
            detected_ids.append(entry_id)
            applied_ids.append(entry_id)
        merged_constraints = merge_supported_constraints(merged_constraints, entry.get("constraints", {}))

    return {
        "detected_constraint_ids": detected_ids,
        "applied_constraint_ids": applied_ids,
        "constraints": merged_constraints,
    }

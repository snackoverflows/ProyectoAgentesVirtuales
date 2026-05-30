import json
import re
from typing import Any, Dict


def extract_json_object(raw_text: str) -> Dict[str, Any]:
    stripped = (raw_text or "").strip()
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    fenced_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", stripped, re.DOTALL)
    if fenced_match:
        parsed = json.loads(fenced_match.group(1).strip())
        if isinstance(parsed, dict):
            return parsed

    first_object = stripped.find("{")
    last_object = stripped.rfind("}")
    if first_object != -1 and last_object != -1 and last_object > first_object:
        parsed = json.loads(stripped[first_object:last_object + 1])
        if isinstance(parsed, dict):
            return parsed

    raise ValueError("No valid JSON object found in payload.")

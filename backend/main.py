# main.py
"""CLI runner para probar la generacion de horarios con un JSON de entrada.

Uso:
- stdin:
  python main.py < input.json
- archivo:
  python main.py --input input.json
- argumento directo:
  python main.py '{"courses": [...], "constraints": {...}}'

El JSON esperado sigue el contrato de ActionModule:
{
  "courses": [
    {
      "course": "Bases de Datos",
      "group": "A",
      "professor": "Perez",
      "meetings": [
        {"day": "Lunes", "start": "08:00", "end": "10:00"},
        {"day": "Miércoles", "start": "10:00", "end": "12:00"}
      ]
    }
  ],
  "constraints": {
    "hard": {...},
    "soft": {...},
    "weights": {...}
  },
  "max_per_day": 3,
  "top_n": 3
}

Regla clave:
- Cada objeto en `courses` es una seccion/grupo.
- `meetings` son bloques obligatorios dentro de esa seccion.
- Si hay varias entradas con el mismo `course`, son alternativas y se elige solo una.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict

from action_module import ActionModule


def load_payload() -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description="Prueba local de generacion de horarios")
    parser.add_argument(
        "payload",
        nargs="?",
        help="JSON inline con courses y constraints, o dejar vacio para leer stdin",
    )
    parser.add_argument(
        "--input",
        "-i",
        dest="input_file",
        help="Ruta a un archivo JSON con courses y constraints",
    )
    args = parser.parse_args()

    raw_text = ""
    if args.input_file:
        with open(args.input_file, "r", encoding="utf-8") as file_handle:
            raw_text = file_handle.read()
    elif args.payload:
        raw_text = args.payload
    else:
        raw_text = sys.stdin.read()

    raw_text = raw_text.strip()
    if not raw_text:
        raise ValueError("No se recibio payload JSON. Usa --input, un argumento directo o stdin.")

    return json.loads(raw_text)


def build_report(payload: Dict[str, Any]) -> Dict[str, Any]:
    action_module = ActionModule()

    courses = payload.get("courses", [])
    constraints = payload.get("constraints", {})
    max_per_day = int(payload.get("max_per_day", 3))
    top_n = int(payload.get("top_n", 3))

    # Generate all valid schedules and compute scores so we can normalize to 1-10
    all_valid = action_module.generate_all_schedules(courses, constraints, max_per_day)
    scored = [(action_module.score_schedule(s, constraints), s) for s in all_valid]
    scored.sort(key=lambda x: x[0], reverse=True)

    warnings = []
    best = [s for score, s in scored[:top_n]]
    if best:
      validation = action_module.validate_schedule(best[0])
      warnings.extend(validation.get("warnings", []))

    # Normalize scores to 1-10 (1 decimal)
    scores_only = [sc for sc, _ in scored]
    if scores_only:
      max_score = max(scores_only)
      min_score = min(scores_only)
    else:
      max_score = min_score = 0

    def score_to_1_10(raw: int) -> float:
      if max_score == min_score:
        return round(10.0, 1) if raw > 0 else 1.0
      norm = (raw - min_score) / (max_score - min_score)
      val = 1.0 + norm * 9.0
      return round(val, 1)

    enriched = []
    for raw_score, sched in scored[:top_n]:
      distinct_courses = len({b.get("course") for b in sched if b.get("course")})
      distinct_days = len({b.get("day") for b in sched if b.get("day")})
      enriched.append({
        "meta": {
          "score_1_10": score_to_1_10(raw_score),
          "raw_score": raw_score,
          "distinct_courses": distinct_courses,
          "distinct_days": distinct_days,
        },
        "blocks": sched,
      })

    return {
      "text": (
        f"Se generaron {len(enriched)} horarios válidos."
        if enriched
        else "No se encontraron horarios válidos con las restricciones indicadas."
      ),
      "schedules": enriched,
      "warnings": warnings,
    }


def main() -> int:
    try:
        payload = load_payload()
        report = build_report(payload)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        error_report = {"error": str(exc)}
        print(json.dumps(error_report, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

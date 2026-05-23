"""CLI runner para chatear con el LLM y generar horarios con confirmacion.

Uso:
- stdin:
  python main_llm.py < input.txt
- argumento directo (modo single-turn):
    python main_llm.py "Quiero un horario sin tardes"
- plantilla base opcional:
  python main_llm.py --template input.json --output output.json "Quiero..."

Modo interactivo:
- ejecuta `python main_llm.py` sin argumentos,
- el chat va acumulando el borrador en memoria,
- `output.json` se actualiza con el estado actual,
- `schedule.json` solo se genera cuando confirmas que deseas producir horarios.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from action_module import ActionModule
from memory_module import MemoryModule
from llm_module import LLMModule


DEFAULT_TOP_N = 3
USER_ID = "local_user"
SESSION_ID = "terminal_chat"


def load_json_file(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as file_handle:
        return json.load(file_handle)


def read_user_text(typed_text: Optional[str]) -> str:
    if typed_text is not None:
        return typed_text.strip()
    if sys.stdin.isatty():
        return ""
    return sys.stdin.read().strip()


def extract_json_payload(raw_text: str) -> Dict[str, Any]:
    stripped = raw_text.strip()

    try:
        return json.loads(stripped)
    except Exception:
        pass

    fenced_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", stripped, re.DOTALL)
    if fenced_match:
        candidate = fenced_match.group(1).strip()
        return json.loads(candidate)

    first_object = stripped.find("{")
    last_object = stripped.rfind("}")
    if first_object != -1 and last_object != -1 and last_object > first_object:
        candidate = stripped[first_object:last_object + 1]
        return json.loads(candidate)

    raise ValueError("LLM no devolvio un JSON valido")


def build_default_template() -> Dict[str, Any]:
    return {
        "courses": [],
        "constraints": {
            "hard": [],
            "soft": [],
            "optimization": {"objectives": []},
            "scoring": {"mode": "fixed", "per": 30},
        },
    }


def build_initial_chat_state(template_payload: Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(template_payload.get("courses"), list) and isinstance(template_payload.get("constraints"), dict):
        draft = {
            "courses": template_payload.get("courses", []),
            "constraints": template_payload.get("constraints", {}),
        }
        if template_payload.get("max_per_day") is not None:
            draft["max_per_day"] = template_payload.get("max_per_day")
        if template_payload.get("top_n") is not None:
            draft["top_n"] = template_payload.get("top_n")
        return draft
    return build_default_template()


def _normalize_optional_int(payload: Dict[str, Any], key: str, default_value: int) -> Tuple[int, str]:
    raw_value = payload.get(key)
    if raw_value is None:
        return default_value, "default"
    try:
        return int(raw_value), "input"
    except (TypeError, ValueError):
        return default_value, "default_invalid"


def _normalize_optional_max_per_day(payload: Dict[str, Any]) -> Tuple[Optional[int], str]:
    raw_value = payload.get("max_per_day")
    if raw_value is None:
        return None, "unset"
    try:
        return int(raw_value), "input"
    except (TypeError, ValueError):
        return None, "unset_invalid"


def build_schedule_report(payload: Dict[str, Any]) -> Dict[str, Any]:
    action_module = ActionModule()

    courses = payload.get("courses", [])
    constraints = payload.get("constraints", {})
    max_per_day, max_per_day_source = _normalize_optional_max_per_day(payload)
    top_n, top_n_source = _normalize_optional_int(payload, "top_n", DEFAULT_TOP_N)

    all_valid = action_module.generate_all_schedules(courses, constraints, max_per_day)
    scored = [(action_module.score_schedule(schedule, constraints), schedule) for schedule in all_valid]
    scored.sort(key=lambda item: item[0], reverse=True)

    warnings = []
    selected = [schedule for score, schedule in scored[:top_n]]
    if selected:
        validation = action_module.validate_schedule(selected[0])
        warnings.extend(validation.get("warnings", []))

    results = []
    for raw_score, schedule in scored[:top_n]:
        results.append(
            {
                "meta": {
                    "raw_score": raw_score,
                    "distinct_courses": len({block.get("course") for block in schedule if block.get("course")}),
                    "distinct_days": len({block.get("day") for block in schedule if block.get("day")}),
                },
                "blocks": schedule,
            }
        )

    return {
        "text": (
            f"Se generaron {len(results)} horarios válidos."
            if results
            else "No se encontraron horarios válidos con las restricciones indicadas."
        ),
        "schedules": results,
        "warnings": warnings,
        "execution_params": {
            "max_per_day": max_per_day,
            "max_per_day_source": max_per_day_source,
            "top_n": top_n,
            "top_n_source": top_n_source,
        },
    }


def _load_json_if_valid(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        payload = load_json_file(path)
    except Exception:
        return None
    if isinstance(payload, dict) and isinstance(payload.get("courses"), list) and isinstance(payload.get("constraints"), dict):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("draft"), dict):
        return payload.get("draft")
    return None


def _print_help() -> None:
    print(
        "Comandos: /help, /show, /generate, /reset, /exit\n"
        "Escribe tu preferencia o curso en lenguaje natural.\n"
        "Cuando el borrador esté listo, el chat te pedirá confirmación antes de generar horarios.")


def _looks_like_yes(text: str) -> bool:
    normalized = text.strip().casefold()
    return normalized in {"si", "sí", "s", "ok", "dale", "genera", "generar", "adelante", "yes", "y"}


def _looks_like_no(text: str) -> bool:
    normalized = text.strip().casefold()
    return normalized in {"no", "n", "cancelar", "stop", "parar", "no generes"}


def save_output_state(output_path: Path, state: Dict[str, Any]) -> None:
    output_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def save_schedule_state(schedule_output_path: Path, report: Dict[str, Any]) -> None:
    schedule_output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def run_generation_from_draft(draft: Dict[str, Any]) -> Dict[str, Any]:
    return build_schedule_report(draft)


def run_chat_mode(
    llm_module: LLMModule,
    memory_module: MemoryModule,
    initial_draft: Dict[str, Any],
    output_path: Path,
    schedule_output_path: Path,
) -> int:
    draft_state = initial_draft
    awaiting_confirmation = False
    last_assistant_state: Dict[str, Any] = {
        "assistant_message": "",
        "draft": draft_state,
        "status": "collecting",
        "missing_items": [],
        "should_generate": False,
    }

    print("Chat de horarios listo. Escribe /help para ver comandos.")
    _print_help()

    while True:
        try:
            user_text = input("tu> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSaliendo.")
            return 0

        if not user_text:
            continue

        lower_text = user_text.casefold()

        if lower_text in {"/exit", "exit", "salir", "quit"}:
            print("Saliendo.")
            return 0

        if lower_text in {"/help", "help"}:
            _print_help()
            continue

        if lower_text == "/reset":
            memory_module.clear_memory(USER_ID, SESSION_ID)
            draft_state = build_default_template()
            awaiting_confirmation = False
            last_assistant_state = {
                "assistant_message": "Borrador reiniciado.",
                "draft": draft_state,
                "status": "collecting",
                "missing_items": [],
                "should_generate": False,
            }
            save_output_state(output_path, last_assistant_state)
            print("assistant> Borrador reiniciado.")
            continue

        if lower_text == "/show":
            print(json.dumps(draft_state, ensure_ascii=False, indent=2))
            continue

        memory_module.add_message("user", user_text, USER_ID, SESSION_ID)
        history = memory_module.get_last_messages(n=12, user_id=USER_ID, session_id=SESSION_ID)

        if awaiting_confirmation and _looks_like_no(user_text):
            awaiting_confirmation = False
            assistant_message = "De acuerdo. Dime qué quieres ajustar y sigo construyendo el borrador."
            last_assistant_state = {
                "assistant_message": assistant_message,
                "draft": draft_state,
                "status": "collecting",
                "missing_items": [],
                "should_generate": False,
            }
            memory_module.add_message("assistant", assistant_message, USER_ID, SESSION_ID)
            save_output_state(output_path, last_assistant_state)
            print(f"assistant> {assistant_message}")
            continue

        if awaiting_confirmation and _looks_like_yes(user_text):
            schedule_report = run_generation_from_draft(draft_state)
            save_schedule_state(schedule_output_path, schedule_report)
            assistant_message = f"Listo. Generé los horarios y los guardé en {schedule_output_path.name}."
            last_assistant_state = {
                "assistant_message": assistant_message,
                "draft": draft_state,
                "status": "generated",
                "missing_items": [],
                "should_generate": True,
            }
            memory_module.add_message("assistant", assistant_message, USER_ID, SESSION_ID)
            save_output_state(output_path, last_assistant_state)
            print(f"assistant> {assistant_message}")
            print(json.dumps(schedule_report, ensure_ascii=False, indent=2))
            awaiting_confirmation = False
            continue

        if lower_text in {"/generate", "generate", "generar"}:
            schedule_report = run_generation_from_draft(draft_state)
            save_schedule_state(schedule_output_path, schedule_report)
            assistant_message = f"Listo. Generé los horarios y los guardé en {schedule_output_path.name}."
            last_assistant_state = {
                "assistant_message": assistant_message,
                "draft": draft_state,
                "status": "generated",
                "missing_items": [],
                "should_generate": True,
            }
            memory_module.add_message("assistant", assistant_message, USER_ID, SESSION_ID)
            save_output_state(output_path, last_assistant_state)
            print(f"assistant> {assistant_message}")
            print(json.dumps(schedule_report, ensure_ascii=False, indent=2))
            awaiting_confirmation = False
            continue

        raw_llm_text = llm_module.generate_schedule_chat_turn(user_text, current_draft=draft_state, history=history)
        parsed = extract_json_payload(raw_llm_text)

        draft_state = parsed.get("draft", draft_state)
        awaiting_confirmation = parsed.get("status") == "awaiting_confirmation"
        assistant_message = parsed.get("assistant_message", "")
        missing_items = parsed.get("missing_items", [])
        last_assistant_state = {
            "assistant_message": assistant_message,
            "draft": draft_state,
            "status": parsed.get("status", "collecting"),
            "missing_items": missing_items,
            "should_generate": bool(parsed.get("should_generate", False)),
        }

        memory_module.add_message("assistant", assistant_message, USER_ID, SESSION_ID, metadata={"state": last_assistant_state})
        save_output_state(output_path, last_assistant_state)

        print(f"assistant> {assistant_message}")
        if missing_items:
            print(f"assistant> Faltan: {', '.join(missing_items)}")
        if awaiting_confirmation:
            print("assistant> Si quieres, responde 'sí' para generar los horarios.")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Previsualiza la interpretacion del LLM para horarios")
    parser.add_argument(
        "prompt",
        nargs="?",
        help="Texto libre del usuario; si se omite, se lee desde stdin",
    )
    parser.add_argument(
        "--template",
        "-t",
        dest="template_file",
        help="Ruta a un JSON base con courses y constraints para usar como contexto",
    )
    parser.add_argument(
        "--output",
        "-o",
        dest="output_file",
        default="output.json",
        help="Archivo de salida donde se guardara la interpretacion estructurada",
    )
    parser.add_argument(
        "--schedule-output",
        dest="schedule_output_file",
        default="schedule.json",
        help="Archivo de salida para los horarios generados por ActionModule",
    )
    args = parser.parse_args()

    user_text = read_user_text(args.prompt)
    is_interactive = not user_text and sys.stdin.isatty()

    template_payload: Dict[str, Any] = build_default_template()
    if args.template_file:
        template_path = Path(args.template_file)
        template_payload = load_json_file(template_path)
    elif not is_interactive and Path("input.json").exists():
        loaded_template = _load_json_if_valid(Path("input.json"))
        if loaded_template is not None:
            template_payload = loaded_template

    llm_module = LLMModule()
    memory_module = MemoryModule()

    output_path = Path(args.output_file)
    schedule_output_path = Path(args.schedule_output_file)

    if is_interactive:
        initial_draft = _load_json_if_valid(output_path) or build_initial_chat_state(template_payload)
        return run_chat_mode(
            llm_module=llm_module,
            memory_module=memory_module,
            initial_draft=initial_draft,
            output_path=output_path,
            schedule_output_path=schedule_output_path,
        )

    if not user_text:
        print(json.dumps({"error": "No se recibio texto para interpretar"}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1

    raw_llm_text = llm_module.generate_schedule_input(user_text, template_payload=template_payload)
    try:
        interpreted_payload = extract_json_payload(raw_llm_text)
        output_path.write_text(
            json.dumps(interpreted_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        schedule_report = build_schedule_report(interpreted_payload)
        schedule_output_path.write_text(
            json.dumps(schedule_report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        print(
            json.dumps(
                {
                    "status": "ok",
                    "output_file": str(output_path),
                    "schedule_output_file": str(schedule_output_path),
                    "raw_text": raw_llm_text,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except Exception as exc:
        failure_payload = {
            "error": f"No se pudo convertir la respuesta del LLM a JSON: {exc}",
            "raw_text": raw_llm_text,
        }
        output_path.write_text(
            json.dumps(failure_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(json.dumps({"status": "error", "output_file": str(output_path), "raw_text": raw_llm_text}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
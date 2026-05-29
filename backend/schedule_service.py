import json
import re
from typing import Any, Dict, List, Optional, Tuple

import constraints as constraints_module


class ScheduleService:
    def __init__(self, memory_module, llm_module, action_module, error_handler, default_emotion_profile: str):
        self.memory_module = memory_module
        self.llm_module = llm_module
        self.action_module = action_module
        self.error_handler = error_handler
        self.default_emotion_profile = default_emotion_profile

    def build_default_schedule_draft(self) -> Dict[str, Any]:
        return {
            "courses": [],
            "constraints": {
                "hard": [],
                "soft": [],
                "optimization": {"objectives": []},
                "scoring": {"mode": "fixed", "per": 30},
            },
        }

    def get_latest_schedule_draft(self, user_id: str, session_id: str) -> Dict[str, Any]:
        history = self.memory_module.get_last_messages(n=20, user_id=user_id, session_id=session_id)
        for entry in reversed(history):
            metadata = entry.get("metadata") or {}
            state = metadata.get("state")
            if isinstance(state, dict) and isinstance(state.get("draft"), dict):
                return state.get("draft")
        return self.build_default_schedule_draft()

    def detect_clear_intent(self, user_text: str) -> Dict[str, bool]:
        lowered = (user_text or "").strip().lower()
        wants_clear = "limpiar" in lowered or "borrar" in lowered or "vaciar" in lowered or "resetear" in lowered
        if not wants_clear:
            return {"clear_courses": False, "clear_constraints": False, "clear_schedules": False}
        return {
            "clear_courses": "curso" in lowered or "cursos" in lowered,
            "clear_constraints": "restriccion" in lowered or "restricciones" in lowered,
            "clear_schedules": "horario" in lowered or "horarios" in lowered,
        }

    def extract_json_payload(self, raw_text: str) -> Dict[str, Any]:
        stripped = raw_text.strip()
        try:
            return json.loads(stripped)
        except Exception:
            pass

        fenced_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", stripped, re.DOTALL)
        if fenced_match:
            return json.loads(fenced_match.group(1).strip())

        first_object = stripped.find("{")
        last_object = stripped.rfind("}")
        if first_object != -1 and last_object != -1 and last_object > first_object:
            return json.loads(stripped[first_object:last_object + 1])

        raise ValueError("LLM no devolvio un JSON valido")

    def _normalize_optional_int(self, payload: Dict[str, Any], key: str, default_value: int) -> Tuple[int, str]:
        raw_value = payload.get(key)
        if raw_value is None:
            return default_value, "default"
        try:
            return int(raw_value), "input"
        except (TypeError, ValueError):
            return default_value, "default_invalid"

    def _normalize_optional_max_per_day(self, payload: Dict[str, Any]) -> Tuple[Optional[int], str]:
        raw_value = payload.get("max_per_day")
        if raw_value is None:
            return None, "unset"
        try:
            return int(raw_value), "input"
        except (TypeError, ValueError):
            return None, "unset_invalid"

    def _is_canonical_meeting(self, meeting: Dict[str, Any]) -> bool:
        return (
            isinstance(meeting, dict)
            and set(meeting.keys()).issubset({"day", "start", "end"})
            and isinstance(meeting.get("day"), str)
            and isinstance(meeting.get("start"), str)
            and isinstance(meeting.get("end"), str)
        )

    def _is_canonical_course(self, course: Dict[str, Any]) -> bool:
        if not isinstance(course, dict):
            return False
        if set(course.keys()) - {"course", "group", "professor", "meetings", "tags"}:
            return False
        if not isinstance(course.get("course"), str) or not isinstance(course.get("group"), str) or not isinstance(course.get("professor"), str):
            return False
        meetings = course.get("meetings")
        return isinstance(meetings, list) and all(self._is_canonical_meeting(meeting) for meeting in meetings)

    def _is_canonical_draft(self, draft: Dict[str, Any]) -> bool:
        if not isinstance(draft, dict):
            return False
        if set(draft.keys()) != {"courses", "constraints"}:
            return False
        courses = draft.get("courses")
        constraints = draft.get("constraints")
        if not isinstance(courses, list) or not isinstance(constraints, dict):
            return False
        return all(self._is_canonical_course(course) for course in courses)

    def _validate_draft_constraints(self, draft: Dict[str, Any]) -> List[str]:
        if not isinstance(draft, dict):
            return ["El borrador no es un objeto JSON valido."]
        constraints = draft.get("constraints", {})
        if not isinstance(constraints, dict):
            return ["constraints debe ser un objeto."]
        return constraints_module.validate_constraints(constraints)

    def _build_contract_violation_message(self) -> str:
        return "Necesito corregir el formato del borrador antes de generar. Revisa cursos y restricciones para continuar."

    def enforce_schedule_contract(self, parsed_state: Dict[str, Any], current_draft: Dict[str, Any], warnings: List[str]) -> Dict[str, Any]:
        assistant_message = parsed_state.get("assistant_message") or "Sigo construyendo el borrador del horario."
        draft = parsed_state.get("draft", current_draft)
        state = {
            "assistant_message": assistant_message,
            "draft": draft,
            "status": parsed_state.get("status", "collecting"),
            "missing_items": parsed_state.get("missing_items", []),
            "should_generate": bool(parsed_state.get("should_generate", False)),
        }

        contract_errors: List[str] = []
        if not self._is_canonical_draft(draft):
            contract_errors.append("El borrador devuelto por el LLM no respeta el template canonico.")
        contract_errors.extend(self._validate_draft_constraints(draft))

        if contract_errors:
            state["status"] = "collecting"
            state["should_generate"] = False
            state["assistant_message"] = self._build_contract_violation_message()
            warnings.append("Las restricciones no cumplen el contrato canonico y se bloqueo la generacion.")
            warnings.extend(contract_errors)
        return state

    def build_schedule_report(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        courses = payload.get("courses", [])
        constraints = payload.get("constraints", {})
        max_per_day, max_per_day_source = self._normalize_optional_max_per_day(payload)
        top_n, top_n_source = self._normalize_optional_int(payload, "top_n", 3)

        all_valid = self.action_module.get_best_schedules(courses, constraints, max_per_day=max_per_day, top_n=top_n)
        warnings: List[str] = []
        if all_valid:
            warnings.extend(self.action_module.validate_schedule(all_valid[0]).get("warnings", []))

        schedule_rows: List[Dict[str, Any]] = []
        total_courses = len({course.get("course") for course in courses if isinstance(course, dict) and course.get("course")}) or 1
        for schedule in all_valid:
            raw_score = self.action_module.score_schedule(schedule, constraints)
            user_score, user_score_breakdown = self._compute_user_score(
                schedule=schedule,
                total_courses=total_courses,
                constraints=constraints,
            )
            schedule_rows.append(
                {
                    "meta": {
                        "raw_score": raw_score,
                        "user_score": user_score,
                        "user_score_breakdown": user_score_breakdown,
                        "distinct_courses": len({block.get("course") for block in schedule if block.get("course")}),
                        "distinct_days": len({block.get("day") for block in schedule if block.get("day")}),
                    },
                    "blocks": schedule,
                }
            )

        return {
            "text": f"Se generaron {len(schedule_rows)} horarios validos." if schedule_rows else "No se encontraron horarios validos con las restricciones indicadas.",
            "schedules": schedule_rows,
            "warnings": warnings,
            "execution_params": {
                "max_per_day": max_per_day,
                "max_per_day_source": max_per_day_source,
                "top_n": top_n,
                "top_n_source": top_n_source,
            },
        }

    def _compute_user_score(
        self,
        schedule: List[Dict[str, Any]],
        total_courses: int,
        constraints: Dict[str, Any],
    ) -> Tuple[int, Dict[str, float]]:
        distinct_courses = len({block.get("course") for block in schedule if block.get("course")})
        distinct_days = len({block.get("day") for block in schedule if block.get("day")})

        coverage_ratio = min(1.0, max(0.0, distinct_courses / max(1, total_courses)))
        day_efficiency = max(0.0, min(1.0, 1.0 - ((max(1, distinct_days) - 1) / 6.0)))

        normalized = constraints_module.normalize_constraints(constraints)
        soft_raw = constraints_module.evaluate_soft(schedule, normalized)
        soft_component = (soft_raw / (abs(soft_raw) + 10.0)) if soft_raw != 0 else 0.0
        soft_ratio = max(0.0, min(1.0, (soft_component + 1.0) / 2.0))

        objectives = (constraints.get("optimization") or {}).get("objectives") or []
        hard_rules = constraints.get("hard") or []
        soft_rules = constraints.get("soft") or []

        has_day_intent = any(
            isinstance(obj, dict) and obj.get("target") == "days_on_campus"
            for obj in objectives
        ) or any(
            isinstance(rule, dict) and (
                rule.get("type") == "day"
                or (rule.get("type") == "metric" and rule.get("target") == "days_on_campus")
            )
            for rule in (hard_rules + soft_rules)
        )

        has_soft_rules = isinstance(soft_rules, list) and len(soft_rules) > 0

        # Politica UX:
        # - Sin intencion explicita sobre dias: priorizar combinacion de cursos.
        # - Con intencion sobre dias: incluir eficiencia de dias como criterio visible.
        if has_day_intent and has_soft_rules:
            weighted = (0.70 * coverage_ratio) + (0.20 * day_efficiency) + (0.10 * soft_ratio)
        elif has_day_intent:
            weighted = (0.80 * coverage_ratio) + (0.20 * day_efficiency)
        elif has_soft_rules:
            weighted = (0.90 * coverage_ratio) + (0.10 * soft_ratio)
        else:
            weighted = coverage_ratio

        user_score = int(round(weighted * 100))
        user_score = max(0, min(100, user_score))

        return user_score, {
            "coverage_ratio": round(coverage_ratio, 3),
            "day_efficiency": round(day_efficiency, 3),
            "soft_ratio": round(soft_ratio, 3),
            "has_day_intent": 1.0 if has_day_intent else 0.0,
            "has_soft_rules": 1.0 if has_soft_rules else 0.0,
        }

    def run_schedule_workflow(
        self,
        user_text: str,
        user_id: str,
        session_id: str,
        normalize_emotion_profile,
        log_debug,
    ) -> Tuple[str, List[str], Dict[str, Any], Optional[Dict[str, Any]], str]:
        warnings: List[str] = []
        current_draft = self.get_latest_schedule_draft(user_id, session_id)
        conversation_history = self.memory_module.get_last_messages(n=12, user_id=user_id, session_id=session_id)

        raw_llm_text = self.error_handler.run_with_retry(
            self.llm_module.generate_schedule_chat_turn,
            user_text,
            current_draft=current_draft,
            history=conversation_history,
            fallback=json.dumps(
                {
                    "assistant_message": "No pude interpretar el borrador de horarios en este momento.",
                    "draft": current_draft,
                    "status": "collecting",
                    "missing_items": [],
                    "should_generate": False,
                },
                ensure_ascii=False,
            ),
        )
        log_debug("llm.schedule.raw", raw_llm_text)

        try:
            parsed_state = self.extract_json_payload(raw_llm_text)
        except Exception:
            parsed_state = {
                "assistant_message": raw_llm_text,
                "draft": current_draft,
                "status": "collecting",
                "missing_items": [],
                "should_generate": False,
            }

        log_debug("llm.schedule.parsed", parsed_state)
        state = self.enforce_schedule_contract(parsed_state, current_draft, warnings)
        emotion_profile = normalize_emotion_profile(parsed_state.get("emotion_profile", self.default_emotion_profile))

        schedule_report: Optional[Dict[str, Any]] = None
        if state["should_generate"]:
            schedule_report = self.error_handler.run_with_retry(
                self.build_schedule_report,
                state["draft"],
                fallback={
                    "text": "No se encontraron horarios validos con las restricciones indicadas.",
                    "schedules": [],
                    "warnings": ["No se pudo generar el horario."],
                    "execution_params": {
                        "max_per_day": None,
                        "max_per_day_source": "unset",
                        "top_n": 3,
                        "top_n_source": "default",
                    },
                },
            )
            warnings.extend(schedule_report.get("warnings", []))
            log_debug("schedule.report", schedule_report)

        assistant_message = state.get("assistant_message") or "Sigo construyendo el borrador del horario."
        self.memory_module.add_message(
            "assistant",
            assistant_message,
            user_id,
            session_id,
            metadata={"state": state, "emotion_profile": emotion_profile},
        )

        return assistant_message, warnings, state, schedule_report, emotion_profile

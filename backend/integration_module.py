from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Tuple, Iterator, Literal, Dict, Any
import base64
import json
import os
import re
import constraints as constraints_module

from input_module import InputModule
from memory_module import MemoryModule
from llm_module import LLMModule
from action_module import ActionModule
from tts_module import TTSModule
from stt_module import STTModule
from output_module import OutputModule
from error_module import ErrorHandler

app = FastAPI(title="Agente Virtual Backend")

input_module = InputModule()
memory_module = MemoryModule()
llm_module = LLMModule()
action_module = ActionModule()
tts_module = TTSModule()
stt_module = STTModule()
output_module = OutputModule()
error_handler = ErrorHandler(retries=3, delay=2)

AVAILABLE_EMOTION_PROFILES = llm_module.available_emotion_profiles
DEFAULT_EMOTION_PROFILE = AVAILABLE_EMOTION_PROFILES[0] if AVAILABLE_EMOTION_PROFILES else "neutral"

DEBUG_LOGS = os.getenv("BACKEND_DEBUG_LOGS", "").strip().lower() in {"1", "true", "yes", "on"}


class AgentRequest(BaseModel):
    content: str
    user_id: Optional[str] = "user1"
    session_id: Optional[str] = "default"
    tts_mode: Literal["auto", "stream", "batch"] = "auto"
    workflow: Literal["chat", "schedule"] = "chat"


class AgentResponse(BaseModel):
    text: str
    audio_base64: str
    emotion_profile: str
    animation: Optional[str] = None
    emotion: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    state: Optional[Dict[str, Any]] = None
    state_json: Optional[str] = None
    schedule_report: Optional[Dict[str, Any]] = None
    schedule_json: Optional[str] = None


def _log_debug(label: str, payload: Any) -> None:
    if not DEBUG_LOGS:
        return
    try:
        rendered = json.dumps(payload, ensure_ascii=False, indent=2) if isinstance(payload, (dict, list)) else str(payload)
    except Exception:
        rendered = str(payload)
    print(f"[DEBUG] {label}: {rendered}")


def _normalize_emotion_profile(value: Any) -> str:
    if not isinstance(value, str):
        return DEFAULT_EMOTION_PROFILE
    normalized = value.strip().lower()
    return normalized if normalized in AVAILABLE_EMOTION_PROFILES else DEFAULT_EMOTION_PROFILE


def _parse_agent_response_payload(raw_text: str) -> Dict[str, Any]:
    stripped = raw_text.strip()
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    fenced_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", stripped, re.DOTALL)
    if fenced_match:
        parsed = json.loads(fenced_match.group(1).strip())
        if isinstance(parsed, dict):
            return parsed

    return {"text": stripped, "emotion_profile": DEFAULT_EMOTION_PROFILE}


def _extract_json_payload(raw_text: str) -> Dict[str, Any]:
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


def _build_default_schedule_draft() -> Dict[str, Any]:
    return {
        "courses": [],
        "constraints": {
            "hard": [],
            "soft": [],
            "optimization": {"objectives": []},
            "scoring": {"mode": "fixed", "per": 30},
        },
    }


def _get_latest_schedule_draft(user_id: str, session_id: str) -> Dict[str, Any]:
    history = memory_module.get_last_messages(n=20, user_id=user_id, session_id=session_id)
    for entry in reversed(history):
        metadata = entry.get("metadata") or {}
        state = metadata.get("state")
        if isinstance(state, dict) and isinstance(state.get("draft"), dict):
            return state.get("draft")
    return _build_default_schedule_draft()


def _detect_clear_intent(user_text: str) -> Dict[str, bool]:
    lowered = (user_text or "").strip().lower()
    wants_clear = "limpiar" in lowered or "borrar" in lowered or "vaciar" in lowered or "resetear" in lowered
    if not wants_clear:
        return {"clear_courses": False, "clear_constraints": False, "clear_schedules": False}
    return {
        "clear_courses": "curso" in lowered or "cursos" in lowered,
        "clear_constraints": "restriccion" in lowered or "restricciones" in lowered,
        "clear_schedules": "horario" in lowered or "horarios" in lowered,
    }


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


def _is_canonical_meeting(meeting: Dict[str, Any]) -> bool:
    return (
        isinstance(meeting, dict)
        and set(meeting.keys()).issubset({"day", "start", "end"})
        and isinstance(meeting.get("day"), str)
        and isinstance(meeting.get("start"), str)
        and isinstance(meeting.get("end"), str)
    )


def _is_canonical_course(course: Dict[str, Any]) -> bool:
    if not isinstance(course, dict):
        return False
    if set(course.keys()) - {"course", "group", "professor", "meetings", "tags"}:
        return False
    if not isinstance(course.get("course"), str) or not isinstance(course.get("group"), str) or not isinstance(course.get("professor"), str):
        return False
    meetings = course.get("meetings")
    return isinstance(meetings, list) and all(_is_canonical_meeting(meeting) for meeting in meetings)


def _is_canonical_draft(draft: Dict[str, Any]) -> bool:
    if not isinstance(draft, dict):
        return False
    if set(draft.keys()) != {"courses", "constraints"}:
        return False
    courses = draft.get("courses")
    constraints = draft.get("constraints")
    if not isinstance(courses, list) or not isinstance(constraints, dict):
        return False
    return all(_is_canonical_course(course) for course in courses)


def _validate_draft_constraints(draft: Dict[str, Any]) -> List[str]:
    if not isinstance(draft, dict):
        return ["El borrador no es un objeto JSON valido."]
    constraints = draft.get("constraints", {})
    if not isinstance(constraints, dict):
        return ["constraints debe ser un objeto."]
    return constraints_module.validate_constraints(constraints)


def _build_contract_violation_message() -> str:
    return "Necesito corregir el formato del borrador antes de generar. Revisa cursos y restricciones para continuar."


def _enforce_schedule_contract(
    parsed_state: Dict[str, Any],
    current_draft: Dict[str, Any],
    warnings: List[str],
) -> Dict[str, Any]:
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
    if not _is_canonical_draft(draft):
        contract_errors.append("El borrador devuelto por el LLM no respeta el template canonico.")
    contract_errors.extend(_validate_draft_constraints(draft))

    if contract_errors:
        state["status"] = "collecting"
        state["should_generate"] = False
        state["assistant_message"] = _build_contract_violation_message()
        warnings.append("Las restricciones no cumplen el contrato canonico y se bloqueo la generacion.")
        warnings.extend(contract_errors)

    return state


def _build_schedule_report(payload: Dict[str, Any]) -> Dict[str, Any]:
    courses = payload.get("courses", [])
    constraints = payload.get("constraints", {})
    max_per_day, max_per_day_source = _normalize_optional_max_per_day(payload)
    top_n, top_n_source = _normalize_optional_int(payload, "top_n", 3)

    all_valid = action_module.get_best_schedules(courses, constraints, max_per_day=max_per_day, top_n=top_n)
    warnings: List[str] = []

    if all_valid:
        validation = action_module.validate_schedule(all_valid[0])
        warnings.extend(validation.get("warnings", []))

    schedule_rows: List[Dict[str, Any]] = []
    for schedule in all_valid:
        raw_score = action_module.score_schedule(schedule, constraints)
        schedule_rows.append(
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


def _run_schedule_workflow(req: AgentRequest, user_text: str) -> Tuple[str, List[str], Dict[str, Any], Optional[Dict[str, Any]], str]:
    warnings: List[str] = []
    current_draft = _get_latest_schedule_draft(req.user_id, req.session_id)
    conversation_history = memory_module.get_last_messages(n=12, user_id=req.user_id, session_id=req.session_id)

    raw_llm_text = error_handler.run_with_retry(
        llm_module.generate_schedule_chat_turn,
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
    _log_debug("llm.schedule.raw", raw_llm_text)

    try:
        parsed_state = _extract_json_payload(raw_llm_text)
    except Exception:
        parsed_state = {
            "assistant_message": raw_llm_text,
            "draft": current_draft,
            "status": "collecting",
            "missing_items": [],
            "should_generate": False,
        }

    _log_debug("llm.schedule.parsed", parsed_state)

    state = _enforce_schedule_contract(parsed_state, current_draft, warnings)
    emotion_profile = _normalize_emotion_profile(parsed_state.get("emotion_profile", DEFAULT_EMOTION_PROFILE))

    schedule_report: Optional[Dict[str, Any]] = None
    if state["should_generate"]:
        schedule_report = error_handler.run_with_retry(
            _build_schedule_report,
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
        _log_debug("schedule.report", schedule_report)

    assistant_message = state.get("assistant_message") or "Sigo construyendo el borrador del horario."
    memory_module.add_message(
        "assistant",
        assistant_message,
        req.user_id,
        req.session_id,
        metadata={"state": state, "emotion_profile": emotion_profile},
    )

    return assistant_message, warnings, state, schedule_report, emotion_profile


def _run_chat_workflow(req: AgentRequest, user_text: str) -> Tuple[str, List[str], Optional[Dict[str, Any]], Optional[Dict[str, Any]], str]:
    warnings: List[str] = []
    conversation_history = memory_module.get_last_messages(n=10, user_id=req.user_id, session_id=req.session_id)

    agent_prompt = llm_module.build_agent_response_prompt(AVAILABLE_EMOTION_PROFILES)
    raw_llm_response = error_handler.run_with_retry(
        llm_module.generate_response,
        user_text,
        history=conversation_history,
        system_prompt=agent_prompt,
        fallback=json.dumps(
            {
                "text": "Lo siento, no pude generar una respuesta en este momento.",
                "emotion_profile": DEFAULT_EMOTION_PROFILE,
            },
            ensure_ascii=False,
        ),
    )

    _log_debug("llm.chat.raw", raw_llm_response)
    parsed_response = _parse_agent_response_payload(raw_llm_response)
    _log_debug("llm.chat.parsed", parsed_response)
    llm_response = parsed_response.get("text") or raw_llm_response
    emotion_profile = _normalize_emotion_profile(parsed_response.get("emotion_profile", DEFAULT_EMOTION_PROFILE))

    memory_module.add_message(
        "assistant",
        llm_response,
        req.user_id,
        req.session_id,
        metadata={"emotion_profile": emotion_profile},
    )
    return llm_response, warnings, None, None, emotion_profile


def _build_output_with_tts(
    req: AgentRequest,
    llm_response: str,
    warnings: List[str],
    state: Optional[Dict[str, Any]],
    schedule_report: Optional[Dict[str, Any]],
    emotion_profile: str,
) -> Dict[str, Any]:
    audio_bytes, tts_warnings = error_handler.run_with_retry(
        tts_module.synthesize,
        llm_response,
        mode=req.tts_mode,
        fallback=(b"", ["No se pudo generar audio TTS."]),
    )
    warnings.extend(tts_warnings)

    return output_module.create_output(
        text=llm_response,
        audio_bytes=audio_bytes,
        emotion_profile=emotion_profile,
        warnings=warnings,
        state=state,
        schedule_report=schedule_report,
    )


def _build_agent_response(req: AgentRequest) -> Tuple[str, List[str], Optional[Dict[str, Any]], Optional[Dict[str, Any]], str]:
    entry = input_module.capture_text(req.content, req.user_id, req.session_id)
    if entry is None:
        return "El mensaje de texto esta vacio.", ["Se recibio un texto vacio."], None, None, DEFAULT_EMOTION_PROFILE

    user_text = entry["content_text"]
    memory_module.add_message("user", user_text, req.user_id, req.session_id)
    warnings: List[str] = []

    clear_flags = _detect_clear_intent(user_text)
    if any(clear_flags.values()):
        draft = _get_latest_schedule_draft(req.user_id, req.session_id)
        default_draft = _build_default_schedule_draft()

        if clear_flags["clear_courses"]:
            draft["courses"] = []

        if clear_flags["clear_constraints"]:
            draft["constraints"] = default_draft["constraints"]

        state: Dict[str, Any] = {
            "assistant_message": "Listo, limpie lo solicitado.",
            "draft": draft,
            "status": "collecting",
            "missing_items": [],
            "should_generate": False,
        }

        schedule_report: Optional[Dict[str, Any]] = None
        if clear_flags["clear_schedules"]:
            schedule_report = {
                "text": "Horarios limpiados.",
                "schedules": [],
                "warnings": [],
                "execution_params": {
                    "max_per_day": None,
                    "max_per_day_source": "unset",
                    "top_n": 3,
                    "top_n_source": "default",
                },
            }

        memory_module.add_message(
            "assistant",
            state["assistant_message"],
            req.user_id,
            req.session_id,
            metadata={"state": state, "emotion_profile": DEFAULT_EMOTION_PROFILE},
        )
        return state["assistant_message"], warnings, state, schedule_report, DEFAULT_EMOTION_PROFILE

    if req.workflow == "schedule":
        return _run_schedule_workflow(req, user_text)

    return _run_chat_workflow(req, user_text)


@app.post("/agent", response_model=AgentResponse, response_model_exclude_none=True)
async def process_agent(req: AgentRequest):
    llm_response, warnings, state, schedule_report, emotion_profile = _build_agent_response(req)
    return _build_output_with_tts(req, llm_response, warnings, state, schedule_report, emotion_profile)


@app.post("/agent/realtime")
async def process_agent_realtime(req: AgentRequest):
    llm_response, warnings, _, _, emotion_profile = _build_agent_response(req)

    stream_iter, tts_warnings = error_handler.run_with_retry(
        tts_module.stream_with_fallback,
        llm_response,
        mode=req.tts_mode,
        fallback=(iter(()), ["No se pudo iniciar el stream de audio."]),
    )
    warnings.extend(tts_warnings)

    def event_stream() -> Iterator[bytes]:
        meta = {
            "event": "meta",
            "text": llm_response,
            "emotion_profile": emotion_profile,
            "warnings": warnings,
        }
        yield (json.dumps(meta, ensure_ascii=False) + "\n").encode("utf-8")

        try:
            for chunk in stream_iter:
                payload = {
                    "event": "audio_chunk",
                    "audio_base64": base64.b64encode(chunk).decode("utf-8"),
                }
                yield (json.dumps(payload) + "\n").encode("utf-8")
        except Exception:
            fallback_audio = error_handler.run_with_retry(tts_module.generate_audio, llm_response, fallback=b"")
            warning_payload = {
                "event": "warning",
                "message": "Stream interrumpido; se entrega audio en modo batch.",
            }
            yield (json.dumps(warning_payload, ensure_ascii=False) + "\n").encode("utf-8")

            if fallback_audio:
                payload = {
                    "event": "audio_chunk",
                    "audio_base64": base64.b64encode(fallback_audio).decode("utf-8"),
                }
                yield (json.dumps(payload) + "\n").encode("utf-8")

        yield b'{"event":"done"}\n'

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


@app.post("/transcribe", response_model=AgentResponse, response_model_exclude_none=True)
async def transcribe_and_process(
    file: UploadFile = File(...),
    user_id: str = Form("unity_user"),
    session_id: str = Form("default"),
    tts_mode: str = Form("auto"),
    workflow: str = Form("chat"),
):
    try:
        audio_bytes = await file.read()
        mime_type = file.content_type or "audio/wav"
    except Exception as e:
        return {
            "text": "",
            "audio_base64": "",
            "emotion_profile": DEFAULT_EMOTION_PROFILE,
            "warnings": [f"No se pudo leer el archivo de audio: {e}"],
        }

    input_module.capture_audio(audio_bytes, mime_type=mime_type, user_id=user_id, session_id=session_id)

    try:
        transcript = error_handler.run_with_retry(stt_module.transcribe, audio_bytes, mime_type, fallback="")
    except Exception as e:
        return {
            "text": "",
            "audio_base64": "",
            "emotion_profile": DEFAULT_EMOTION_PROFILE,
            "warnings": [f"Error en STT: {e}"],
        }

    if not transcript:
        return {
            "text": "",
            "audio_base64": "",
            "emotion_profile": DEFAULT_EMOTION_PROFILE,
            "warnings": ["STT no devolvio texto."],
        }

    try:
        current_draft = _get_latest_schedule_draft(user_id, session_id)
        conversation_history = memory_module.get_last_messages(n=12, user_id=user_id, session_id=session_id)
        probe_raw = error_handler.run_with_retry(
            llm_module.generate_schedule_chat_turn,
            transcript,
            current_draft=current_draft,
            history=conversation_history,
            fallback="{}",
        )
        _log_debug("stt.transcript", transcript)
        _log_debug("llm.schedule.probe_raw", probe_raw)
        try:
            probe_parsed = _extract_json_payload(probe_raw)
            _log_debug("llm.schedule.probe_parsed", probe_parsed)
            if isinstance(probe_parsed, dict) and (probe_parsed.get("should_generate") or isinstance(probe_parsed.get("draft"), dict)):
                workflow = "schedule"
                _log_debug("llm.schedule.workflow", "forced_schedule")
        except Exception:
            pass
    except Exception:
        pass

    req = AgentRequest(content=transcript, user_id=user_id, session_id=session_id, tts_mode=tts_mode, workflow=workflow)
    llm_response, warnings, state, schedule_report, emotion_profile = _build_agent_response(req)
    return _build_output_with_tts(req, llm_response, warnings, state, schedule_report, emotion_profile)

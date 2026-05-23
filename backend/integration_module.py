# integration_module.py
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Tuple, Iterator, Literal, Dict, Any
import base64
import json
import re

from input_module import InputModule
from memory_module import MemoryModule
from llm_module import LLMModule
from action_module import ActionModule
from tts_module import TTSModule
from output_module import OutputModule
from error_module import ErrorHandler

app = FastAPI(title="Agente Virtual Backend")

# -------- Módulos --------
input_module = InputModule()
memory_module = MemoryModule()
llm_module = LLMModule()
action_module = ActionModule()
tts_module = TTSModule()
output_module = OutputModule()
error_handler = ErrorHandler(retries=3, delay=2)

# -------- Request / Response --------
class AgentRequest(BaseModel):
    content: str
    user_id: Optional[str] = "user1"
    session_id: Optional[str] = "default"
    tts_mode: Literal["auto", "stream", "batch"] = "auto"
    workflow: Literal["chat", "schedule"] = "chat"

class AgentResponse(BaseModel):
    text: str
    audio_base64: str
    animation: str
    emotion: str
    warnings: List[str] = Field(default_factory=list)
    state: Optional[Dict[str, Any]] = None
    state_json: Optional[str] = None
    schedule_report: Optional[Dict[str, Any]] = None
    schedule_json: Optional[str] = None


class TextOnlyResponse(BaseModel):
    text: str
    warnings: List[str] = Field(default_factory=list)


class ScheduleTestRequest(BaseModel):
    courses: List[Dict]
    constraints: Dict = Field(default_factory=dict)
    max_per_day: int = 3
    top_n: int = 3


class ScheduleTestResponse(BaseModel):
    text: str
    schedules: List[List[Dict]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class AgentInterpretResponse(BaseModel):
    raw_text: str
    parsed: Optional[Dict] = None
    warnings: List[str] = Field(default_factory=list)


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
        "text": (
            f"Se generaron {len(schedule_rows)} horarios válidos."
            if schedule_rows
            else "No se encontraron horarios válidos con las restricciones indicadas."
        ),
        "schedules": schedule_rows,
        "warnings": warnings,
        "execution_params": {
            "max_per_day": max_per_day,
            "max_per_day_source": max_per_day_source,
            "top_n": top_n,
            "top_n_source": top_n_source,
        },
    }


def _build_agent_response(req: AgentRequest) -> Tuple[str, List[str], Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    warnings: List[str] = []
    state: Optional[Dict[str, Any]] = None
    schedule_report: Optional[Dict[str, Any]] = None

    # 1. Capturar texto transcrito por Unity (STT en cliente)
    entry = input_module.capture_text(req.content, req.user_id, req.session_id)
    if entry is None:
        return "El mensaje de texto está vacío.", ["Se recibió un texto vacío."], None, None

    user_text = entry["content_text"]
    memory_module.add_message("user", user_text, req.user_id, req.session_id)

    if req.workflow == "schedule":
        current_draft = _get_latest_schedule_draft(req.user_id, req.session_id)
        conversation_history = memory_module.get_last_messages(
            n=12,
            user_id=req.user_id,
            session_id=req.session_id,
        )

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

        assistant_message = parsed_state.get("assistant_message") or "Sigo construyendo el borrador del horario."
        draft = parsed_state.get("draft", current_draft)
        state = {
            "assistant_message": assistant_message,
            "draft": draft,
            "status": parsed_state.get("status", "collecting"),
            "missing_items": parsed_state.get("missing_items", []),
            "should_generate": bool(parsed_state.get("should_generate", False)),
        }

        if not _is_canonical_draft(draft):
            state["status"] = "collecting"
            state["should_generate"] = False
            warnings.append("El borrador devuelto por el LLM no respeta el template canónico.")

        memory_module.add_message("assistant", assistant_message, req.user_id, req.session_id, metadata={"state": state})

        if state["should_generate"]:
            schedule_report = error_handler.run_with_retry(
                _build_schedule_report,
                state["draft"],
                fallback={
                    "text": "No se encontraron horarios válidos con las restricciones indicadas.",
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

        return assistant_message, warnings, state, schedule_report

    # 2. Tomar contexto de memoria por sesión
    conversation_history = memory_module.get_last_messages(
        n=10,
        user_id=req.user_id,
        session_id=req.session_id,
    )

    # 3. Generar respuesta LLM con fallback
    llm_response = error_handler.run_with_retry(
        llm_module.generate_response,
        user_text,
        history=conversation_history,
        fallback="Lo siento, no pude generar una respuesta en este momento."
    )

    # 4. ActionModule condicional por marcador de herramienta
    if llm_response.startswith("TOOL:schedule"):
        courses = [
            {"course": "Bases de Datos", "options": [{"day": "Lunes", "start": "08:00", "end": "10:00"}]},
            {"course": "Redes", "options": [{"day": "Martes", "start": "09:00", "end": "11:00"}]},
        ]
        constraints = {"no_afternoon": True, "exclude_days": ["Viernes"]}
        schedules = error_handler.run_with_retry(
            action_module.get_best_schedules,
            courses,
            constraints,
            top_n=3,
            fallback=[],
        )
        if schedules:
            validation = error_handler.run_with_retry(
                action_module.validate_schedule,
                schedules[0],
                fallback={"warnings": ["No se pudo validar el horario."]},
            )
            warnings.extend(validation.get("warnings", []))

            if schedules[0]:
                schedule_lines = []
                for block in schedules[0]:
                    schedule_lines.append(
                        f"{block['course']} - {block['day']} {block['start']} a {block['end']}"
                    )
                llm_response = "Horario sugerido:\n" + "\n".join(schedule_lines)
        else:
            warnings.append("No se encontraron horarios válidos con las restricciones actuales.")

    # 5. Guardar respuesta en memoria
    memory_module.add_message("assistant", llm_response, req.user_id, req.session_id)
    return llm_response, warnings, state, schedule_report

# -------- Endpoint principal --------
@app.post("/agent", response_model=AgentResponse)
async def process_agent(req: AgentRequest):
    llm_response, warnings, state, schedule_report = _build_agent_response(req)
    audio_bytes, tts_warnings = error_handler.run_with_retry(
        tts_module.synthesize,
        llm_response,
        mode=req.tts_mode,
        fallback=(b"", ["No se pudo generar audio TTS."]),
    )
    warnings.extend(tts_warnings)

    output_json = output_module.create_output(
        text=llm_response,
        audio_bytes=audio_bytes,
        animation="talk",
        emotion="friendly",
        warnings=warnings,
        state=state,
        schedule_report=schedule_report,
    )

    return output_json


@app.post("/agent/realtime")
async def process_agent_realtime(req: AgentRequest):
    llm_response, warnings, _, _ = _build_agent_response(req)

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
            "animation": "talk",
            "emotion": "friendly",
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
            fallback_audio = error_handler.run_with_retry(
                tts_module.generate_audio,
                llm_response,
                fallback=b"",
            )
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


@app.post("/agent/text-only", response_model=TextOnlyResponse)
async def process_agent_text_only(req: AgentRequest):
    llm_response, warnings, _, _ = _build_agent_response(req)
    return TextOnlyResponse(text=llm_response, warnings=warnings)


@app.post("/schedule/test", response_model=ScheduleTestResponse)
async def test_schedule_generation(req: ScheduleTestRequest):
    schedules = error_handler.run_with_retry(
        action_module.get_best_schedules,
        req.courses,
        req.constraints,
        max_per_day=req.max_per_day,
        top_n=req.top_n,
        fallback=[],
    )

    warnings: List[str] = []
    if schedules:
        validation = error_handler.run_with_retry(
            action_module.validate_schedule,
            schedules[0],
            fallback={"warnings": ["No se pudo validar el horario."]},
        )
        warnings.extend(validation.get("warnings", []))
        text = f"Se generaron {len(schedules)} horarios válidos."
    else:
        text = "No se encontraron horarios válidos con las restricciones indicadas."
        warnings.append(text)

    return ScheduleTestResponse(text=text, schedules=schedules, warnings=warnings)


@app.post("/agent/interpret", response_model=AgentInterpretResponse)
async def interpret_agent(req: AgentRequest):
    """Interpret input libre con LLM y devolver JSON estructurado si es posible.

    El LLM debe responder preferiblemente con un JSON como:
    {"intent":"create_schedule","requires_schedule":true,"entities":{...}}
    """
    warnings: List[str] = []

    entry = input_module.capture_text(req.content, req.user_id, req.session_id)
    if entry is None:
        return AgentInterpretResponse(raw_text="", parsed=None, warnings=["Mensaje vacío"]) 

    conversation_history = memory_module.get_last_messages(
        n=10, user_id=req.user_id, session_id=req.session_id
    )

    parser_prompt = (
        "Actúa como un parser: extrae intención y entidades de este texto y devuelve SOLO un JSON. "
        "Formato esperado: {\"intent\": str, \"requires_schedule\": bool, \"entities\": {...}}\n\n"
        f"Input: {req.content}"
    )

    llm_response = error_handler.run_with_retry(
        llm_module.generate_response,
        parser_prompt,
        history=conversation_history,
        fallback=""
    )

    parsed = None
    try:
        parsed = json.loads(llm_response)
    except Exception:
        warnings.append("LLM no devolvió JSON válido; revisar raw_text.")

    return AgentInterpretResponse(raw_text=llm_response, parsed=parsed, warnings=warnings)
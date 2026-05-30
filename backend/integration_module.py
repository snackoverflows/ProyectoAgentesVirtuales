from fastapi import FastAPI, File, UploadFile, Form
from pydantic import BaseModel, Field
from typing import Optional, List, Tuple, Literal, Dict, Any
import json
import os

from input_module import InputModule
from memory_module import MemoryModule
from llm_module import LLMModule
from action_module import ActionModule
from tts_module import TTSModule
from stt_module import STTModule
from output_module import OutputModule
from error_module import ErrorHandler
from schedule_service import ScheduleService
from chat_service import ChatService
from audio_service import AudioService

app = FastAPI(title="Agente Virtual Backend")

input_module = InputModule()
memory_module = MemoryModule()
llm_module = LLMModule()
action_module = ActionModule()
tts_module = TTSModule()
stt_module = STTModule()
output_module = OutputModule()

# Retry tuning knobs (latency-focused defaults)
llm_error_handler = ErrorHandler(
    retries=int(os.getenv("LLM_RETRIES", "2")),
    delay=float(os.getenv("LLM_RETRY_DELAY", "0.4")),
)
stt_error_handler = ErrorHandler(
    retries=int(os.getenv("STT_RETRIES", "2")),
    delay=float(os.getenv("STT_RETRY_DELAY", "0.3")),
)
tts_error_handler = ErrorHandler(
    retries=int(os.getenv("TTS_RETRIES", "1")),
    delay=float(os.getenv("TTS_RETRY_DELAY", "0.2")),
)

AVAILABLE_EMOTION_PROFILES = llm_module.available_emotion_profiles
DEFAULT_EMOTION_PROFILE = AVAILABLE_EMOTION_PROFILES[0] if AVAILABLE_EMOTION_PROFILES else "neutral"

schedule_service = ScheduleService(
    memory_module=memory_module,
    llm_module=llm_module,
    action_module=action_module,
    error_handler=llm_error_handler,
    default_emotion_profile=DEFAULT_EMOTION_PROFILE,
)
chat_service = ChatService(
    memory_module=memory_module,
    llm_module=llm_module,
    error_handler=llm_error_handler,
    available_emotion_profiles=AVAILABLE_EMOTION_PROFILES,
    default_emotion_profile=DEFAULT_EMOTION_PROFILE,
)
audio_service = AudioService(
    tts_module=tts_module,
    stt_module=stt_module,
    output_module=output_module,
    tts_error_handler=tts_error_handler,
    stt_error_handler=stt_error_handler,
    default_emotion_profile=DEFAULT_EMOTION_PROFILE,
)

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


def _build_agent_response(req: AgentRequest) -> Tuple[str, List[str], Optional[Dict[str, Any]], Optional[Dict[str, Any]], str]:
    entry = input_module.capture_text(req.content, req.user_id, req.session_id)
    if entry is None:
        return "El mensaje de texto esta vacio.", ["Se recibio un texto vacio."], None, None, DEFAULT_EMOTION_PROFILE

    user_text = entry["content_text"]
    memory_module.add_message("user", user_text, req.user_id, req.session_id)

    clear_flags = schedule_service.detect_clear_intent(user_text)
    if any(clear_flags.values()):
        draft = schedule_service.get_latest_schedule_draft(req.user_id, req.session_id)
        default_draft = schedule_service.build_default_schedule_draft()

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
        return state["assistant_message"], [], state, schedule_report, DEFAULT_EMOTION_PROFILE

    if req.workflow == "schedule":
        return schedule_service.run_schedule_workflow(
            user_text=user_text,
            user_id=req.user_id,
            session_id=req.session_id,
            normalize_emotion_profile=_normalize_emotion_profile,
            log_debug=_log_debug,
        )

    return chat_service.run_chat_workflow(
        user_text=user_text,
        user_id=req.user_id,
        session_id=req.session_id,
        normalize_emotion_profile=_normalize_emotion_profile,
        log_debug=_log_debug,
    )


@app.post("/agent", response_model=AgentResponse, response_model_exclude_none=True)
async def process_agent(req: AgentRequest):
    llm_response, warnings, state, schedule_report, emotion_profile = _build_agent_response(req)
    return audio_service.build_output_with_tts(
        tts_mode=req.tts_mode,
        llm_response=llm_response,
        warnings=warnings,
        state=state,
        schedule_report=schedule_report,
        emotion_profile=emotion_profile,
    )


@app.post("/agent/realtime")
async def process_agent_realtime(req: AgentRequest):
    llm_response, warnings, _, _, emotion_profile = _build_agent_response(req)
    return audio_service.build_realtime_stream_response(
        tts_mode=req.tts_mode,
        llm_response=llm_response,
        warnings=warnings,
        emotion_profile=emotion_profile,
    )


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

    transcript = audio_service.transcribe(audio_bytes, mime_type)
    if not transcript:
        return {
            "text": "",
            "audio_base64": "",
            "emotion_profile": DEFAULT_EMOTION_PROFILE,
            "warnings": ["STT no devolvio texto."],
        }

    normalized_workflow = workflow if workflow in {"chat", "schedule"} else "chat"
    req = AgentRequest(content=transcript, user_id=user_id, session_id=session_id, tts_mode=tts_mode, workflow=normalized_workflow)
    llm_response, warnings, state, schedule_report, emotion_profile = _build_agent_response(req)
    return audio_service.build_output_with_tts(
        tts_mode=req.tts_mode,
        llm_response=llm_response,
        warnings=warnings,
        state=state,
        schedule_report=schedule_report,
        emotion_profile=emotion_profile,
    )

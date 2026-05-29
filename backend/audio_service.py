from typing import Any, Dict, List, Optional


class AudioService:
    def __init__(self, tts_module, stt_module, output_module, tts_error_handler, stt_error_handler, default_emotion_profile: str):
        self.tts_module = tts_module
        self.stt_module = stt_module
        self.output_module = output_module
        self.tts_error_handler = tts_error_handler
        self.stt_error_handler = stt_error_handler
        self.default_emotion_profile = default_emotion_profile

    def build_output_with_tts(
        self,
        tts_mode: str,
        llm_response: str,
        warnings: List[str],
        state: Optional[Dict[str, Any]],
        schedule_report: Optional[Dict[str, Any]],
        emotion_profile: str,
    ) -> Dict[str, Any]:
        audio_bytes, tts_warnings = self.tts_error_handler.run_with_retry(
            self.tts_module.synthesize,
            llm_response,
            mode=tts_mode,
            fallback=(b"", ["No se pudo generar audio TTS."]),
        )
        warnings.extend(tts_warnings)
        return self.output_module.create_output(
            text=llm_response,
            audio_bytes=audio_bytes,
            emotion_profile=emotion_profile,
            warnings=warnings,
            state=state,
            schedule_report=schedule_report,
        )

    def transcribe(self, audio_bytes: bytes, mime_type: str = "audio/wav") -> str:
        return self.stt_error_handler.run_with_retry(self.stt_module.transcribe, audio_bytes, mime_type, fallback="")

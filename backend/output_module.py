# output_module.py
import base64
import json
from typing import List, Dict, Optional, Any

class OutputModule:
    """
    Módulo que construye la salida del agente para frontend / Unity.
    Contiene:
        - texto (respuesta del LLM)
        - audio (bytes TTS en base64)
        - metadata (animaciones, emociones, advertencias)
    """

    def __init__(self):
        self.default_emotion_profile = "neutral"

    def create_output(
        self,
        text: str,
        audio_bytes: Optional[bytes] = None,
        emotion_profile: Optional[str] = None,
        animation: Optional[str] = None,
        emotion: Optional[str] = None,
        warnings: Optional[List[str]] = None,
        state: Optional[Dict[str, Any]] = None,
        schedule_report: Optional[Dict[str, Any]] = None,
    ) -> Dict:
        """
        Genera la salida lista para enviar al frontend.
        """
        if audio_bytes:
            audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
        else:
            audio_base64 = ""

        output = {
            "text": text,
            "audio_base64": audio_base64,
            "emotion_profile": emotion_profile or self.default_emotion_profile,
            "warnings": warnings or [],
        }

        if animation is not None:
            output["animation"] = animation

        if emotion is not None:
            output["emotion"] = emotion

        if state is not None:
            output["state"] = state
            output["state_json"] = json.dumps(state, ensure_ascii=False, indent=2)

        if schedule_report is not None:
            output["schedule_report"] = schedule_report
            output["schedule_json"] = json.dumps(schedule_report, ensure_ascii=False, indent=2)

        return output
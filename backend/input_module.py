from typing import Optional, Dict, Any
import datetime


class InputModule:
    """
    Input Module para LangChain.
    Recibe texto o audio, normaliza y devuelve dict uniforme.
    """

    def __init__(self):
        self.history = []

    def _build_entry(
        self,
        input_type: str,
        content: Any,
        user_id: str,
        session_id: str,
        mime_type: Optional[str] = None,
    ) -> Dict:
        entry = {
            "type": input_type,
            "content": content,
            "user": user_id,
            "session_id": session_id,
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
        }
        if mime_type:
            entry["mime_type"] = mime_type
        return entry

    def capture_text(
        self,
        text: str,
        user_id: str = "user1",
        session_id: str = "default",
    ) -> Optional[Dict]:
        text = text.strip()
        if not text:
            return None

        entry = self._build_entry("text", text, user_id, session_id)
        entry["content_text"] = text
        entry["audio_bytes"] = None

        self.history.append(entry)
        return entry

    def capture_audio(
        self,
        audio_bytes: bytes,
        mime_type: str = "audio/wav",
        user_id: str = "user1",
        session_id: str = "default",
    ) -> Optional[Dict]:
        if not audio_bytes:
            return None

        entry = self._build_entry("audio", audio_bytes, user_id, session_id, mime_type)
        entry["content_text"] = None
        entry["audio_bytes"] = audio_bytes

        self.history.append(entry)
        return entry

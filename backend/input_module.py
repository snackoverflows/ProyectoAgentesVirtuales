# input_module.py
from typing import Optional, Dict, List, Any
import datetime

class InputModule:
    """
    Input Module para LangChain.
    Recibe texto o audio, normaliza y devuelve dict uniforme.
    """

    def __init__(self):
        # Historial de inputs, se puede usar para LangChain memory
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
            "timestamp": datetime.datetime.utcnow().isoformat(),
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
        """
        Recibe texto, limpia espacios, y lo agrega al historial.
        """
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
        """
        Recibe audio en bytes y lo agrega al historial.
        La conversión a texto (STT) se hará en otro módulo/backend.
        """
        if not audio_bytes:
            return None

        entry = self._build_entry("audio", audio_bytes, user_id, session_id, mime_type)
        entry["content_text"] = None
        entry["audio_bytes"] = audio_bytes

        self.history.append(entry)
        return entry

    def get_latest_input(self, user_id: Optional[str] = None, session_id: Optional[str] = None) -> Optional[Dict]:
        """
        Devuelve el último input del usuario.
        """
        entries: List[Dict] = self.history
        if user_id is not None:
            entries = [item for item in entries if item.get("user") == user_id]
        if session_id is not None:
            entries = [item for item in entries if item.get("session_id") == session_id]
        return entries[-1] if entries else None

    def get_history(self, user_id: Optional[str] = None, session_id: Optional[str] = None):
        """
        Devuelve el historial completo de inputs.
        """
        entries = self.history
        if user_id is not None:
            entries = [item for item in entries if item.get("user") == user_id]
        if session_id is not None:
            entries = [item for item in entries if item.get("session_id") == session_id]
        return entries
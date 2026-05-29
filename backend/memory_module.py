# memory_module.py
from typing import List, Dict, Optional
import datetime

class MemoryModule:
    """
    Módulo de memoria para agentes conversacionales.
    Guarda historial de interacciones y permite acceder al contexto.
    """

    def __init__(self):
        # Historial segmentado por usuario y sesión
        self.histories: Dict[str, List[Dict]] = {}

    def _scope_key(self, user_id: str, session_id: str) -> str:
        return f"{user_id}:{session_id}"

    def add_message(
        self,
        role: str,
        content: str,
        user_id: str = "user1",
        session_id: str = "default",
        metadata: dict = None,
    ):
        """
        Agrega un mensaje al historial.
        role: 'user' o 'assistant'
        content: texto
        user_id: identificador del usuario
        session_id: identificador de sesión
        metadata: diccionario opcional
        """
        entry = {
            "role": role,
            "content": content,
            "user": user_id,
            "session_id": session_id,
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
        }
        if metadata:
            entry["metadata"] = metadata

        scope = self._scope_key(user_id, session_id)
        self.histories.setdefault(scope, []).append(entry)

    def get_last_messages(self, n: int = 10, user_id: str = "user1", session_id: str = "default") -> List[Dict]:
        """
        Devuelve los últimos n mensajes para contexto.
        """
        scope = self._scope_key(user_id, session_id)
        history = self.histories.get(scope, [])
        return history[-n:] if len(history) >= n else history

    def clear_memory(self, user_id: Optional[str] = None, session_id: Optional[str] = None):
        """
        Limpia todo el historial o un ámbito específico.
        """
        if user_id is None and session_id is None:
            self.histories = {}
            return

        if user_id is not None and session_id is not None:
            self.histories.pop(self._scope_key(user_id, session_id), None)
            return

        if user_id is not None:
            keys = [key for key in self.histories if key.startswith(f"{user_id}:")]
        else:
            keys = [key for key in self.histories if key.endswith(f":{session_id}")]

        for key in keys:
            self.histories.pop(key, None)

    def get_full_history(self, user_id: Optional[str] = None, session_id: Optional[str] = None) -> List[Dict]:
        """
        Devuelve todo el historial completo.
        """
        if user_id is None and session_id is None:
            combined: List[Dict] = []
            for history in self.histories.values():
                combined.extend(history)
            return combined

        if user_id is not None and session_id is not None:
            return self.histories.get(self._scope_key(user_id, session_id), [])

        if user_id is not None:
            combined: List[Dict] = []
            for key, history in self.histories.items():
                if key.startswith(f"{user_id}:"):
                    combined.extend(history)
            return combined

        combined: List[Dict] = []
        for key, history in self.histories.items():
            if key.endswith(f":{session_id}"):
                combined.extend(history)
        return combined

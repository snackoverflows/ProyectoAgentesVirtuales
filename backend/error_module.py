# error_module.py
from typing import Callable, Any
import time

class ErrorHandler:
    """
    Módulo para manejo de errores y reintentos.
    Se puede usar para LLM, STT o TTS.
    """

    def __init__(self, retries: int = 3, delay: float = 2.0):
        """
        retries: número de reintentos
        delay: segundos entre reintentos
        """
        self.retries = retries
        self.delay = delay

    def run_with_retry(self, func: Callable, *args, fallback: Any = None, **kwargs) -> Any:
        """
        Ejecuta una función con reintentos automáticos.
        Devuelve el resultado de la función o un fallback explícito.
        """
        last_error = None
        for attempt in range(1, self.retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                print(f"[ErrorHandler] Intento {attempt} falló: {e}")
                time.sleep(self.delay)

        # Si falla todos los intentos, retorna un fallback explícito cuando exista.
        print("[ErrorHandler] Todos los intentos fallaron.")
        if fallback is not None:
            return fallback() if callable(fallback) else fallback
        raise last_error

    def fallback(self, func_name: str, error: Exception) -> dict:
        """
        Retorna un fallback genérico según la función que falló.
        """
        if "generate_content" in func_name:  # LLM
            return {"text": "Lo siento, no pude generar la respuesta ahora.", "error": str(error)}
        elif "transcribe" in func_name:  # STT
            return {"text": "", "error": "No se pudo transcribir el audio."}
        elif "text_to_speech" in func_name or "tts" in func_name:  # TTS
            return b""  # retorna bytes vacíos
        else:
            return {"text": "", "error": str(error)}
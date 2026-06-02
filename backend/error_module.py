from typing import Callable, Any
import time


class ErrorHandler:
    """
    Modulo para manejo de errores y reintentos.
    """

    def __init__(self, retries: int = 3, delay: float = 2.0):
        self.retries = retries
        self.delay = delay
        self.last_error_message = ""
        self.last_error_type = ""

    def run_with_retry(
        self,
        func: Callable,
        *args,
        fallback: Any = None,
        retries: int = None,
        delay: float = None,
        **kwargs,
    ) -> Any:
        effective_retries = self.retries if retries is None else int(retries)
        effective_delay = self.delay if delay is None else float(delay)

        last_error = None
        self.last_error_message = ""
        self.last_error_type = ""
        for attempt in range(1, effective_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                self.last_error_message = str(e)
                self.last_error_type = type(e).__name__
                print(f"[ErrorHandler] Intento {attempt} fallo: {e}")
                if attempt < effective_retries:
                    time.sleep(effective_delay)

        print("[ErrorHandler] Todos los intentos fallaron.")
        if fallback is not None:
            return fallback() if callable(fallback) else fallback
        raise last_error

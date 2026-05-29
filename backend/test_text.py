import argparse
import json
from typing import Any, Dict

from integration_module import AgentRequest, _build_agent_response, output_module


class TextBackendTester:
    """
    Runner de prueba para conversar por texto con el backend sin STT/TTS.
    Reutiliza el flujo normal de schedule para obtener:
    - state.draft (courses + constraints)
    - schedule_report (schedules)
    """

    def __init__(self, user_id: str = "dev_user", session_id: str = "test_text"):
        self.user_id = user_id
        self.session_id = session_id

    def ask(self, content: str, workflow: str = "schedule") -> Dict[str, Any]:
        req = AgentRequest(
            content=content,
            user_id=self.user_id,
            session_id=self.session_id,
            tts_mode="batch",
            workflow=workflow,
        )

        llm_response, warnings, state, schedule_report, emotion_profile = _build_agent_response(req)

        # Sin TTS: audio_bytes vacio para no invocar servicios de voz.
        return output_module.create_output(
            text=llm_response,
            audio_bytes=b"",
            emotion_profile=emotion_profile,
            warnings=warnings,
            state=state,
            schedule_report=schedule_report,
        )


def _print_turn_result(result: Dict[str, Any]) -> None:
    payload = {
        "text": result.get("text"),
        "emotion_profile": result.get("emotion_profile"),
        "warnings": result.get("warnings", []),
        "state": result.get("state"),
        "schedule_report": result.get("schedule_report"),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Prueba textual del backend sin STT/TTS.")
    parser.add_argument("--user-id", default="dev_user")
    parser.add_argument("--session-id", default="test_text")
    parser.add_argument("--workflow", choices=["chat", "schedule"], default="schedule")
    parser.add_argument(
        "--message",
        default="",
        help="Si se indica, ejecuta un solo turno y termina.",
    )
    args = parser.parse_args()

    tester = TextBackendTester(user_id=args.user_id, session_id=args.session_id)

    if args.message:
        result = tester.ask(args.message, workflow=args.workflow)
        _print_turn_result(result)
        return

    print("Modo interactivo (texto). Escribe 'exit' para salir.")
    while True:
        user_text = input("\nTú: ").strip()
        if user_text.lower() in {"exit", "quit", "salir"}:
            print("Fin de la sesión.")
            break
        if not user_text:
            continue

        result = tester.ask(user_text, workflow=args.workflow)
        _print_turn_result(result)


if __name__ == "__main__":
    main()

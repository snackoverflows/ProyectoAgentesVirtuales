from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv


def load_project_env() -> None:
    backend_dir = Path(__file__).resolve().parent
    load_dotenv(backend_dir / "config.env", override=False)
    load_dotenv(override=False)

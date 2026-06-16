from __future__ import annotations

import json
from pathlib import Path

from benchmarks.io import load_jsonl

def main() -> None:
    project_root = Path(__file__).resolve().parents[3]
    summary_dir = project_root / "backend/benchmarks/outputs/summary"
    summary = {
        "summary_files": sorted(str(path) for path in summary_dir.rglob("*.jsonl") if path.is_file()),
        "provider_assessment_template": str(
            project_root / "backend/benchmarks/reports/provider_assessment_template.jsonl"
        ),
    }
    llm_summary = summary_dir / "llm_summary.jsonl"
    stt_summary = summary_dir / "stt_summary.jsonl"
    tts_summary = summary_dir / "tts_summary.jsonl"
    if llm_summary.exists():
        summary["llm_records"] = load_jsonl(llm_summary)
    if stt_summary.exists():
        summary["stt_records"] = load_jsonl(stt_summary)
    if tts_summary.exists():
        summary["tts_records"] = load_jsonl(tts_summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

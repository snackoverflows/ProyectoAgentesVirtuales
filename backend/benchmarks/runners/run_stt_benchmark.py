from __future__ import annotations

import json
import os
from statistics import mean
from pathlib import Path

from dotenv import load_dotenv

from benchmarks.io import load_jsonl, upsert_records, write_csv, write_jsonl
from benchmarks.metrics.wer import compute_wer
from providers import build_stt_provider


def main() -> None:
    project_root = Path(__file__).resolve().parents[3]
    load_dotenv(project_root / "backend" / "config.env", override=False)

    dataset_path = project_root / "backend/benchmarks/datasets/stt/samples.jsonl"
    raw_output_path = project_root / "backend/benchmarks/outputs/raw/stt_runs.jsonl"
    raw_csv_output_path = project_root / "backend/benchmarks/outputs/raw/stt_runs.csv"
    summary_output_path = project_root / "backend/benchmarks/outputs/summary/stt_summary.jsonl"
    summary_csv_output_path = project_root / "backend/benchmarks/outputs/summary/stt_summary.csv"
    repetitions = int(os.getenv("BENCHMARK_REPETITIONS", "5"))
    provider = build_stt_provider()
    raw_records = []
    summary_records = []

    for sample in load_jsonl(dataset_path):
        runs = []
        audio_path = Path(sample["audio_path"])
        if not audio_path.is_absolute():
            audio_path = project_root / audio_path
        for run_index in range(1, repetitions + 1):
            result = provider.transcribe(str(audio_path))
            record = {
                "sample_id": sample["sample_id"],
                "run_index": run_index,
                "provider": provider.provider_name,
                "model": provider.model_name,
                "latency_ms": result.latency_ms,
                "text": result.text,
            }
            raw_records.append(record)
            runs.append(record)

        reference_text = sample["reference_text"]
        hypothesis_text = runs[-1]["text"] if runs else ""
        summary_records.append(
            {
                "sample_id": sample["sample_id"],
                "provider": provider.provider_name,
                "model": provider.model_name,
                "avg_latency_ms": mean(run["latency_ms"] for run in runs),
                "wer": compute_wer(reference_text, hypothesis_text),
                "cost_per_audio_minute": None,
                "customization_notes": "",
                "privacy_notes": "",
                "integration_notes": "",
            }
        )

    combined_raw_records = upsert_records(
        load_jsonl(raw_output_path),
        raw_records,
        ("sample_id", "provider", "model", "run_index"),
    )
    combined_summary_records = upsert_records(
        load_jsonl(summary_output_path),
        summary_records,
        ("sample_id", "provider", "model"),
    )
    write_jsonl(raw_output_path, combined_raw_records)
    write_csv(raw_csv_output_path, combined_raw_records)
    write_jsonl(summary_output_path, combined_summary_records)
    write_csv(summary_csv_output_path, combined_summary_records)
    print(
        json.dumps(
            {
                "summary_output": str(summary_output_path),
                "summary_csv_output": str(summary_csv_output_path),
                "raw_output": str(raw_output_path),
                "raw_csv_output": str(raw_csv_output_path),
                "records": summary_records,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

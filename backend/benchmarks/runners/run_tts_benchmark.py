from __future__ import annotations

import json
import os
import re
from statistics import mean
from pathlib import Path

from dotenv import load_dotenv

from benchmarks.io import load_jsonl, replace_record_groups, upsert_records, write_csv, write_jsonl
from providers import build_tts_provider


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    return normalized or "default"


def main() -> None:
    project_root = Path(__file__).resolve().parents[3]
    load_dotenv(project_root / "backend" / "config.env", override=False)

    dataset_path = project_root / "backend/benchmarks/datasets/tts/samples.jsonl"
    output_dir = project_root / "backend/benchmarks/outputs/raw/tts"
    raw_output_path = project_root / "backend/benchmarks/outputs/raw/tts_runs.jsonl"
    raw_csv_output_path = project_root / "backend/benchmarks/outputs/raw/tts_runs.csv"
    summary_output_path = project_root / "backend/benchmarks/outputs/summary/tts_summary.jsonl"
    summary_csv_output_path = project_root / "backend/benchmarks/outputs/summary/tts_summary.csv"
    detail_csv_output_path = project_root / "backend/benchmarks/outputs/summary/tts_detailed.csv"
    repetitions = int(os.getenv("BENCHMARK_REPETITIONS", "5"))
    output_dir.mkdir(parents=True, exist_ok=True)
    provider = build_tts_provider()
    raw_records = []
    summary_records = []
    wav_providers = {"gemini", "piper", "kokoro"}
    file_extension = ".wav" if provider.provider_name in wav_providers else ".mp3"

    for sample in load_jsonl(dataset_path):
        runs = []
        provider_slug = _slugify(provider.provider_name)
        model_slug = _slugify(provider.model_name)
        for run_index in range(1, repetitions + 1):
            output_path = output_dir / (
                f"{sample['sample_id']}_{provider_slug}_{model_slug}_run_{run_index}{file_extension}"
            )
            result = provider.synthesize(sample["text"], str(output_path))
            record = {
                "sample_id": sample["sample_id"],
                "run_index": run_index,
                "provider": provider.provider_name,
                "model": provider.model_name,
                "latency_ms": result.latency_ms,
                "audio_path": result.audio_path,
            }
            raw_records.append(record)
            runs.append(record)

        summary_records.append(
            {
                "sample_id": sample["sample_id"],
                "provider": provider.provider_name,
                "model": provider.model_name,
                "avg_latency_ms": mean(run["latency_ms"] for run in runs),
                "intelligibility_score": None,
                "naturalness_score": None,
                "cost_per_1k_characters": None,
                "voice_cloning_support": "",
                "pronunciation_control_support": "",
                "privacy_notes": "",
                "integration_notes": "",
            }
        )

    combined_raw_records = replace_record_groups(
        load_jsonl(raw_output_path),
        raw_records,
        ("sample_id", "provider", "model"),
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
    detail_records = []
    for summary in combined_summary_records:
        group_runs = [
            row for row in combined_raw_records
            if row["sample_id"] == summary["sample_id"]
            and row["provider"] == summary["provider"]
            and row["model"] == summary["model"]
        ]
        group_runs.sort(key=lambda row: int(row["run_index"]))
        repetition_count = len(group_runs)
        for row in group_runs:
            detail_records.append(
                {
                    "sample_id": row["sample_id"],
                    "provider": row["provider"],
                    "model": row["model"],
                    "record_type": "run",
                    "run_index": row["run_index"],
                    "repetition_count": repetition_count,
                    "latency_ms": row["latency_ms"],
                    "avg_latency_ms": None,
                    "audio_path": row["audio_path"],
                }
            )
        detail_records.append(
            {
                "sample_id": summary["sample_id"],
                "provider": summary["provider"],
                "model": summary["model"],
                "record_type": "average",
                "run_index": "",
                "repetition_count": repetition_count,
                "latency_ms": None,
                "avg_latency_ms": summary["avg_latency_ms"],
                "audio_path": "",
            }
        )
    write_csv(detail_csv_output_path, detail_records)
    print(
        json.dumps(
            {
                "summary_output": str(summary_output_path),
                "summary_csv_output": str(summary_csv_output_path),
                "detail_csv_output": str(detail_csv_output_path),
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

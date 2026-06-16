# Benchmarking de servicios de IA

Este directorio contiene el arnes reproducible para comparar `LLM`, `STT` y `TTS` sobre el stack final del proyecto.

## Objetivo
El benchmark mide principalmente latencia y deja registradas otras metricas que hoy son:
- automaticas, como `WER` en `STT`
- manuales o pendientes, como `coherence_score`, `instruction_following_score`, `intelligibility_score` y `naturalness_score`

La salida principal para analisis rapido esta en `CSV`. Tambien se escribe `JSONL` por si hace falta reprocesar resultados despues.

## Matriz actual

| Categoria | Provider | Modelo | Requiere API key | Requiere instalacion local | Salida principal |
| --- | --- | --- | --- | --- | --- |
| LLM | Gemini | `gemini-3.1-flash-lite` | Si | No | `llm_summary.csv` |
| LLM | Gemini | `gemini-2.5-flash` | Si | No | `llm_summary.csv` |
| LLM | Groq | `llama-3.1-8b-instant` | Si | No | `llm_summary.csv` |
| LLM | Groq | `qwen/qwen3-32b` | Si | No | `llm_summary.csv` |
| LLM | Ollama | `gemma3` | No | Si | `llm_summary.csv` |
| STT | ElevenLabs | `scribe_v2` | Si | No | `stt_summary.csv` |
| STT | Gemini | `gemini-3.5-flash` | Si | No | `stt_summary.csv` |
| STT | Groq | `whisper-large-v3-turbo` | Si | No | `stt_summary.csv` |
| STT | Whisper | `base` | No | Si | `stt_summary.csv` |
| STT | Moonshine | `es` | No | Si | `stt_summary.csv` |
| TTS | ElevenLabs | `eleven_multilingual_v2` | Si | No | `tts_summary.csv` |
| TTS | ElevenLabs | `eleven_flash_v2_5` | Si | No | `tts_summary.csv` |
| TTS | Gemini | `gemini-3.1-flash-tts-preview` | Si | No | `tts_summary.csv` |
| TTS | Piper | `es_MX-ald-medium` | No | Si | `tts_summary.csv` |
| TTS | Kokoro | `kokoro-v1.0.onnx` | No | Si | `tts_summary.csv` |

## Resultados actuales
Las corridas actuales usan `3` repeticiones por modelo.

### LLM

| Modelo | Latencia promedio |
| --- | ---: |
| `groq / llama-3.1-8b-instant` | `420.76 ms` |
| `groq / qwen/qwen3-32b` | `1256.37 ms` |
| `gemini / gemini-3.1-flash-lite` | `2676.45 ms` |
| `gemini / gemini-2.5-flash` | `4989.12 ms` |
| `ollama / gemma3` | `6196.65 ms` |

### STT

| Modelo | Latencia promedio | WER |
| --- | ---: | ---: |
| `groq / whisper-large-v3-turbo` | `1296.51 ms` | `0.2424` |
| `whisper / base` | `1354.63 ms` | `0.0909` |
| `elevenlabs / scribe_v2` | `1811.66 ms` | `0.2121` |
| `moonshine / es` | `6728.61 ms` | `0.2121` |
| `gemini / gemini-3.5-flash` | `12590.05 ms` | `0.1515` |

### TTS

| Modelo | Latencia promedio |
| --- | ---: |
| `kokoro / kokoro-v1.0.onnx` | `1391.69 ms` |
| `elevenlabs / eleven_multilingual_v2` | `1432.56 ms` |
| `piper / es_MX-ald-medium` | `2059.10 ms` |
| `elevenlabs / eleven_flash_v2_5` | `5562.80 ms` |
| `gemini / gemini-3.1-flash-tts-preview` | `12798.31 ms` |

## Decisiones de arquitectura
- Los benchmarks usan providers desacoplados de las rutas FastAPI. Esto evita medir ruido del endpoint HTTP cuando lo que se quiere comparar es el proveedor.
- Cada categoria tiene un runner dedicado:
  - `run_llm_benchmark.py`
  - `run_stt_benchmark.py`
  - `run_tts_benchmark.py`
- La seleccion de proveedor y modelo se hace por variables de entorno. No se introdujo un orquestador extra para mantener el flujo simple y facil de reproducir desde consola.
- Los resultados se guardan en `raw` y `summary`.
  - `raw`: una fila por corrida
  - `summary`: una fila por `sample_id + provider + model`
- Los runners hacen `upsert` por clave logica. Si vuelves a correr un modelo, se actualiza solo esa fila y no se pisan los otros resultados.
- En `TTS`, los archivos de audio generados incluyen `sample_id + provider + model + run_index` para no sobrescribirse entre modelos.

## Estructura
- `configs/`
  - referencia documental de configuraciones base
- `datasets/`
  - insumos versionados por categoria
- `metrics/`
  - calculo de metricas automaticas como `WER`
- `outputs/raw/`
  - resultados por corrida en `JSONL` y `CSV`
- `outputs/summary/`
  - promedios agregados en `JSONL` y `CSV`
- `reports/`
  - utilidades o notas para generar activos de reporte
- `runners/`
  - scripts ejecutables por categoria

## Dataset actual
- `LLM`
  - usa `backend/benchmarks/datasets/llm/samples.jsonl`
- `STT`
  - usa `backend/benchmarks/datasets/stt/audio/nora.wav`
  - referencia en `backend/benchmarks/datasets/stt/samples.jsonl`
- `TTS`
  - usa `backend/benchmarks/datasets/tts/samples.jsonl`

## Que hace cada script
- `backend/benchmarks/runners/run_llm_benchmark.py`
  - carga el dataset `LLM`
  - llama al provider activo `BENCHMARK_REPETITIONS` veces por muestra
  - guarda `ttft`, latencia total, texto y resumen agregado
- `backend/benchmarks/runners/run_stt_benchmark.py`
  - carga el dataset `STT`
  - transcribe el audio con el provider activo
  - calcula `WER` usando la referencia textual
  - guarda corridas crudas y resumen agregado
- `backend/benchmarks/runners/run_tts_benchmark.py`
  - carga el dataset `TTS`
  - sintetiza audio con el provider activo
  - guarda archivos generados, latencias y resumen agregado
- `backend/benchmarks/reports/generate_report_assets.py`
  - lee resúmenes existentes y arma un payload util para reportes externos

## Instalacion y prerequisitos
La forma recomendada en Windows es:

```powershell
.\scripts\bootstrap_local.ps1
.\scripts\bootstrap_models.ps1
```

Eso deja preparado el entorno Python y la mayor parte del stack local del benchmark.

### Requisitos comunes
- Python con `backend\.venv`
- `backend/config.env` completado
- acceso a red para Gemini, Groq y ElevenLabs

### LLM
- Gemini
  - `LLM_API_KEY`
- Groq
  - `GROQ_API_KEY`
- Ollama
  - `Ollama` instalado
  - modelo `gemma3` descargado

### STT
- ElevenLabs
  - `ELEVENLABS_API_KEY`
- Gemini
  - `LLM_API_KEY`
- Groq
  - `GROQ_API_KEY`
- Whisper local
  - paquete `openai-whisper`
  - `ffmpeg`
  - `FFMPEG_BINARY` configurado si `ffmpeg` no esta en `PATH`
- Moonshine
  - paquete `moonshine-voice`
  - cache local de modelos

### TTS
- ElevenLabs
  - `ELEVENLABS_API_KEY`
  - `TTS_VOICE_ID`
- Gemini
  - `LLM_API_KEY`
- Piper
  - `piper-tts`
  - `PIPER_MODEL_PATH`
  - opcionalmente `PIPER_CONFIG_PATH`
- Kokoro
  - `kokoro-onnx`
  - `KOKORO_MODEL_PATH`
  - `KOKORO_VOICES_PATH`

## Variables de entorno relevantes
- `BENCHMARK_REPETITIONS`
- `LLM_PROVIDER`, `LLM_MODEL`
- `GROQ_MODEL`, `GROQ_STT_MODEL`
- `STT_PROVIDER`, `STT_MODEL`, `WHISPER_MODEL`, `MOONSHINE_MODEL`
- `TTS_PROVIDER`, `TTS_MODEL`
- `GEMINI_STT_MODEL`, `GEMINI_TTS_MODEL`, `GEMINI_TTS_VOICE`
- `OLLAMA_MODEL`
- `LLM_API_KEY`, `GROQ_API_KEY`, `ELEVENLABS_API_KEY`
- `FFMPEG_BINARY`
- `PIPER_BINARY`, `PIPER_MODEL_PATH`, `PIPER_CONFIG_PATH`
- `KOKORO_MODEL_PATH`, `KOKORO_VOICES_PATH`, `KOKORO_VOICE`, `KOKORO_LANGUAGE`

## Como correr

### Un modelo puntual
Desde la raiz del repo:

```powershell
$env:BENCHMARK_REPETITIONS='3'
$env:STT_PROVIDER='whisper'
& backend\.venv\Scripts\python.exe backend\benchmarks\runners\run_stt_benchmark.py
```

### LLM

```powershell
$env:BENCHMARK_REPETITIONS='3'

$env:LLM_PROVIDER='gemini'; $env:LLM_MODEL='gemini-3.1-flash-lite'; & backend\.venv\Scripts\python.exe backend\benchmarks\runners\run_llm_benchmark.py
$env:LLM_PROVIDER='gemini'; $env:LLM_MODEL='gemini-2.5-flash'; & backend\.venv\Scripts\python.exe backend\benchmarks\runners\run_llm_benchmark.py
$env:LLM_PROVIDER='groq'; $env:GROQ_MODEL='llama-3.1-8b-instant'; & backend\.venv\Scripts\python.exe backend\benchmarks\runners\run_llm_benchmark.py
$env:LLM_PROVIDER='groq'; $env:GROQ_MODEL='qwen/qwen3-32b'; & backend\.venv\Scripts\python.exe backend\benchmarks\runners\run_llm_benchmark.py
$env:LLM_PROVIDER='ollama'; $env:OLLAMA_MODEL='gemma3'; & backend\.venv\Scripts\python.exe backend\benchmarks\runners\run_llm_benchmark.py
```

### STT

```powershell
$env:BENCHMARK_REPETITIONS='3'

$env:STT_PROVIDER='elevenlabs'; $env:STT_MODEL='scribe_v2'; & backend\.venv\Scripts\python.exe backend\benchmarks\runners\run_stt_benchmark.py
$env:STT_PROVIDER='gemini'; $env:GEMINI_STT_MODEL='gemini-3.5-flash'; & backend\.venv\Scripts\python.exe backend\benchmarks\runners\run_stt_benchmark.py
$env:STT_PROVIDER='groq'; $env:GROQ_STT_MODEL='whisper-large-v3-turbo'; & backend\.venv\Scripts\python.exe backend\benchmarks\runners\run_stt_benchmark.py
$env:STT_PROVIDER='whisper'; $env:WHISPER_MODEL='base'; & backend\.venv\Scripts\python.exe backend\benchmarks\runners\run_stt_benchmark.py
$env:STT_PROVIDER='moonshine'; $env:MOONSHINE_MODEL='es'; & backend\.venv\Scripts\python.exe backend\benchmarks\runners\run_stt_benchmark.py
```

### TTS

```powershell
$env:BENCHMARK_REPETITIONS='3'

$env:TTS_PROVIDER='elevenlabs'; $env:TTS_MODEL='eleven_multilingual_v2'; & backend\.venv\Scripts\python.exe backend\benchmarks\runners\run_tts_benchmark.py
$env:TTS_PROVIDER='elevenlabs'; $env:TTS_MODEL='eleven_flash_v2_5'; & backend\.venv\Scripts\python.exe backend\benchmarks\runners\run_tts_benchmark.py
$env:TTS_PROVIDER='gemini'; $env:GEMINI_TTS_MODEL='gemini-3.1-flash-tts-preview'; & backend\.venv\Scripts\python.exe backend\benchmarks\runners\run_tts_benchmark.py
$env:TTS_PROVIDER='piper'; & backend\.venv\Scripts\python.exe backend\benchmarks\runners\run_tts_benchmark.py
$env:TTS_PROVIDER='kokoro'; & backend\.venv\Scripts\python.exe backend\benchmarks\runners\run_tts_benchmark.py
```

### Matriz completa de 15 modelos
Corre las tres secciones anteriores con el mismo valor de `BENCHMARK_REPETITIONS`. Los archivos finales quedan en:
- `backend/benchmarks/outputs/summary/llm_summary.csv`
- `backend/benchmarks/outputs/summary/stt_summary.csv`
- `backend/benchmarks/outputs/summary/tts_summary.csv`

## Como leer las salidas
- `outputs/raw/*.csv`
  - una fila por corrida real
  - sirve para revisar dispersión de latencia
- `outputs/summary/*.csv`
  - una fila por modelo
  - sirve para comparar promedios rapidamente

Campos principales:
- `LLM`
  - `avg_total_latency_ms`
  - `avg_ttft_ms` si el provider lo soporta
- `STT`
  - `avg_latency_ms`
  - `wer`
- `TTS`
  - `avg_latency_ms`

## Estado de metricas
- Ya automaticas:
  - latencia en `LLM`, `STT`, `TTS`
  - `WER` en `STT`
- Aun vacias o manuales:
  - `instruction_following_score`
  - `coherence_score`
  - `intelligibility_score`
  - `naturalness_score`
  - costos

## Politica
- Los benchmarks miden providers, no endpoints HTTP.
- Los artefactos generados no deben commitearse.
- Si vuelves a correr un modelo, su fila se actualiza y las demas se conservan.

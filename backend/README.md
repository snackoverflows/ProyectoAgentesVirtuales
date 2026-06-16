# Backend Agente Virtual - Estado Actual

## Objetivo
Backend para agente conversacional de horarios con:
- entrada de texto (`/agent`) o audio (`/transcribe`),
- salida estructurada para Unity,
- generacion determinista de horarios (ActionModule),
- validacion estricta de contrato para constraints canonicos.

## Endpoints reales

### `POST /agent`
Flujo principal para Unity.

Body:
- `content` (string)
- `user_id` (opcional)
- `session_id` (opcional)
- `tts_mode`: `auto | stream | batch`
- `workflow`: `chat | schedule`

Respuesta:
- `text`
- `audio_base64`
- `emotion_profile`
- `warnings`
- `state` (cuando aplica flujo schedule)
- `schedule_report` (solo si `should_generate=true` y pasa contrato)

### `POST /agent/realtime`
Mismo flujo conversacional, con audio en NDJSON:
- `meta`
- `audio_chunk`
- `warning` (si aplica fallback)
- `done`

### `POST /transcribe`
Recibe audio multipart (`file`), transcribe y procesa como `/agent`.
Usa el `workflow` enviado por cliente (`chat` o `schedule`). No realiza probe extra al LLM.

## Flujo schedule (actual)
1. Se captura texto y se guarda en memoria por `user_id:session_id`.
2. LLM devuelve estado conversacional con `draft`.
3. Se valida contrato canonico:
   - shape de `draft`,
   - constraints DSL valido,
   - operadores/tipos/scopes/metricas permitidos.
4. Si falla contrato:
   - se bloquea generacion (`should_generate=false`, `status=collecting`),
   - se devuelve mensaje de correccion + warnings.
5. Si pasa contrato y `should_generate=true`:
   - ActionModule genera y rankea horarios,
   - se retorna `schedule_report`.

## DSL canonico de constraints
Estructura esperada:

```json
{
  "hard": [],
  "soft": [],
  "optimization": {
    "objectives": [
      {"operator": "maximize", "target": "distinct_courses", "priority": 1}
    ]
  },
  "scoring": {"mode": "fixed", "per": 30}
}
```

Reglas clave:
- Top-level permitido: `hard`, `soft`, `optimization`, `scoring`.
- `optimization` solo permite `objectives`.
- `operator` en objectives: solo `maximize | minimize`.
- Operadores de reglas: `include`, `exclude`, `prefer`, `avoid`, `<=`, `>=`, `==`, `between`, `outside`.
- `day` usa dias en espanol (`Lunes` ... `Domingo`).
- `metric` requiere `target`, y con `<=|>=|==` requiere `value` numerico.

## Politica determinista de ranking
- Siempre se prioriza `distinct_courses` como objetivo base primario.
- Luego se aplican objetivos adicionales (p. ej. `minimize days_on_campus`) para desempate.
- `hard` podan combinaciones inviables antes del ranking.
- `soft` y `optimization` ordenan soluciones validas.

## Pruebas locales
- Instalacion recomendada del backend y benchmarking:

```bash
cd backend
.\.venv\Scripts\python.exe -m pip install -e .[all]
```

Nota: `Kokoro` puede requerir Python `3.10` o `3.11`. En Python `3.13`, el resto del set principal del benchmark si se puede instalar y probar en este mismo entorno.

- Harness textual sin STT/TTS: `backend/test_text.py`
- Ejemplo:

```bash
cd backend
.\.venv\Scripts\python.exe test_text.py
```

## Benchmarking
El backend incluye un benchmark desacoplado de FastAPI en `backend/benchmarks/`.

Sirve para:
- comparar latencia entre modelos `LLM`, `STT` y `TTS`
- calcular `WER` en `STT`
- dejar resultados en `CSV` y `JSONL`

Comandos base:

```powershell
cd backend
$env:BENCHMARK_REPETITIONS='3'
$env:STT_PROVIDER='whisper'
.\.venv\Scripts\python.exe benchmarks\runners\run_stt_benchmark.py
```

Salidas:
- `benchmarks/outputs/raw/*.csv`
- `benchmarks/outputs/summary/*.csv`

Modelos del set actual:
- `LLM`: Gemini, Groq, Ollama
- `STT`: ElevenLabs, Gemini, Groq, Whisper, Moonshine
- `TTS`: ElevenLabs, Gemini, Piper, Kokoro

La guia completa del benchmark, prerequisitos y comandos por modelo vive en [benchmarks/README.md](/abs/path/c:/Users/deanv/OneDrive/Escritorio/Tilapez/ProyectoAgentesVirtuales/backend/benchmarks/README.md).

## Variables de entorno
- `LLM_PROVIDER`, `STT_PROVIDER`, `TTS_PROVIDER`
- `LLM_API_KEY`
- `LLM_MODEL` (opcional)
- `GEMINI_STT_MODEL` (opcional)
- `GEMINI_TTS_MODEL` (opcional)
- `GEMINI_TTS_VOICE` (opcional)
- `GROQ_API_KEY`
- `GROQ_MODEL` (opcional)
- `GROQ_STT_MODEL` (opcional)
- `OLLAMA_MODEL` (opcional)
- `LLM_SYSTEM_PROMPT` (opcional)
- `ELEVENLABS_API_KEY`
- `STT_MODEL` (opcional, `scribe_v2`)
- `TTS_MODEL` (opcional)
- `TTS_OUTPUT_FORMAT` (opcional)
- `TTS_VOICE_ID` (opcional)
- `WHISPER_MODEL` (opcional)
- `MOONSHINE_MODEL` (opcional)
- `PIPER_BINARY`, `PIPER_MODEL_PATH`, `PIPER_CONFIG_PATH`
- `KOKORO_MODEL_PATH`, `KOKORO_VOICE`, `KOKORO_LANGUAGE`
- `BACKEND_DEBUG_LOGS` (opcional)
- `LLM_RETRIES` (opcional, default `2`)
- `LLM_RETRY_DELAY` (opcional, default `0.4`)
- `STT_RETRIES` (opcional, default `2`)
- `STT_RETRY_DELAY` (opcional, default `0.3`)
- `TTS_RETRIES` (opcional, default `1`)
- `TTS_RETRY_DELAY` (opcional, default `0.2`)

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
Puede forzar `workflow=schedule` si el probe de LLM devuelve `draft` o `should_generate`.

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
- Harness textual sin STT/TTS: `backend/test_text.py`
- Ejemplo:

```bash
cd backend
.\.venv\Scripts\python.exe test_text.py
```

## Variables de entorno
- `LLM_API_KEY`
- `LLM_MODEL` (opcional)
- `LLM_SYSTEM_PROMPT` (opcional)
- `ELEVENLABS_API_KEY`
- `TTS_OUTPUT_FORMAT` (opcional)
- `TTS_STREAM_MODEL` (opcional)
- `BACKEND_DEBUG_LOGS` (opcional)

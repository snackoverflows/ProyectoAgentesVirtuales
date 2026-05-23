# Backend Agente Virtual - Arquitectura y Guia de Pruebas

## 1) Objetivo del backend
Este backend modular orquesta un agente virtual corporizado con:

- Entrada principal en texto (el STT ocurre en Unity cliente).
- Respuesta de texto con LLM.
- Generacion de audio con ElevenLabs (modo batch o realtime con fallback).
- Generacion y validacion de horarios con ActionModule.
- Memoria conversacional por usuario y sesion.
- Respuesta estructurada para integracion con Unity.

## 2) Estado actual de decisiones de negocio
- STT en Unity: el backend recibe texto transcrito.
- TTS en backend: siempre se intenta generar audio.
- Realtime habilitado: el backend soporta streaming de audio y cae a batch si falla.
- Memoria por user_id y session_id.
- ActionModule se dispara de forma condicional cuando el LLM devuelve marcador TOOL:schedule.
- Los tags de cursos se agregan solo cuando el usuario confirma que quiere reglas de exclusividad o agrupacion.

## 3) Estructura modular
- input_module.py
  - Normaliza entradas y mantiene historial de entradas.
  - Usa capture_text como ruta principal actual.
- memory_module.py
  - Historial por ambito user_id:session_id.
  - Permite recuperar ultimos mensajes para contexto.
- llm_module.py
  - Conexion con Gemini.
  - Construccion de prompt y respuesta conversacional.
- action_module.py
  - Generacion de combinaciones de horarios.
  - Score de horarios.
  - Validacion de traslapes reales por intervalo.
  - Agrupacion por nombre de curso: si un mismo curso aparece varias veces, esas entradas representan secciones/grupos alternativos.
- tts_module.py
  - TTS batch (convert).
  - TTS stream (realtime por chunks).
  - Fallback automatico stream -> batch.
- output_module.py
  - Construye JSON estandar de salida para cliente.
- error_module.py
  - Reintentos y fallback explicito por llamada.
- integration_module.py
  - API FastAPI.
  - Orquesta el pipeline completo.
  - Incluye endpoints normales, realtime y pruebas locales.

## 4) Flujo principal de datos
### Flujo /agent (texto + audio de salida)
1. Llega texto transcrito desde cliente.
2. InputModule normaliza.
3. MemoryModule guarda mensaje de usuario.
4. LLMModule genera respuesta con contexto de memoria.
5. Si hay TOOL:schedule, ActionModule genera y valida horarios.
6. TTSModule sintetiza audio (auto/stream/batch con fallback).
7. OutputModule arma JSON final.

### Regla de horarios
- Cada entrada de `courses` representa una seccion/grupo del curso.
- Si un mismo `course` aparece varias veces, esas entradas son alternativas y el generador elige solo una por curso.
- Dentro de una seccion, `meetings` contiene los bloques obligatorios que se deben cursar juntos.
- Si una seccion tiene dos dias, no son opciones: ambos dias son obligatorios para esa seccion.
- Todas las materias son opcionales: el generador puede omitir un curso completo si ninguna seccion conviene o si ayuda a resolver conflictos.
- El objetivo principal del ranking es incluir la mayor cantidad de cursos distintos posible.
- Las restricciones y preferencias solo resuelven empates o eliminan combinaciones inviables.
- Si quieres llevar solo un curso distinto por dia, usa `single_course_per_day: true`.
- Si ademas quieres que todos los bloques sean matutinos, usa `no_afternoon: true`.
- Si quieres restringir familias de cursos como arte, agrega `tags` en las secciones y `exclusive_tag_limits` en constraints, pero solo despues de confirmacion del usuario.
- Los constraints duros se podan antes de generar combinaciones.
- Los constraints blandos se dejan para el score con pesos configurables.
- Esto reduce latencia sin perder flexibilidad de preferencia/negociacion.

### Flujo /agent/realtime (texto + streaming de audio)
1. Mismo pipeline conversacional.
2. Se inicia stream NDJSON:
   - evento meta (texto, animacion, emocion, warnings)
   - eventos audio_chunk (audio_base64)
   - evento done
3. Si streaming falla durante la respuesta, cae a batch y envia warning.

## 5) Endpoints disponibles
### POST /agent
Respuesta estandar para Unity:
- text
- audio_base64
- animation
- emotion
- warnings

Body:
- content: texto del usuario
- user_id: opcional
- session_id: opcional
- tts_mode: auto | stream | batch

### POST /agent/realtime
Respuesta de streaming NDJSON con eventos:
- meta
- audio_chunk
- warning (si aplica)
- done

Body:
- content: texto del usuario
- user_id: opcional
- session_id: opcional
- tts_mode: auto | stream | batch

### POST /agent/text-only
Prueba local sin Unity y sin audio de salida.
Ideal para validar flujo conversacional y ActionModule sin costo TTS.

Respuesta:
- text
- warnings

Body:
- content: texto del usuario
- user_id: opcional
- session_id: opcional
- tts_mode: opcional (se ignora en esta ruta)

### POST /schedule/test
Prueba local directa del ActionModule (sin LLM, sin TTS).
Ideal para validar generacion de horarios y conflictos.

Respuesta:
- text
- schedules
- warnings

Body:
- courses: lista de cursos con opciones
- constraints: restricciones
- max_per_day: opcional
- top_n: opcional

Si no hay restricciones, envia al menos la estructura base:
```json
{
  "hard": {},
  "soft": {},
  "weights": {},
  "exclusive_tag_limits": {}
}
```

Para la regla "solo un curso al dia en las mananas", usa:
```json
{
  "hard": {
    "single_course_per_day": true,
    "no_afternoon": true
  },
  "soft": {},
  "weights": {},
  "exclusive_tag_limits": {}
}
```

## 6) Ejemplos de prueba local (sin Unity)
### 6.1 Probar flujo texto->texto
POST /agent/text-only

Payload ejemplo:
{
  "content": "Quiero un horario sin cursos en la tarde",
  "user_id": "dev_user",
  "session_id": "test_1"
}

### 6.2 Probar solo ActionModule
POST /schedule/test

Payload ejemplo:
{
  "courses": [
    {
      "course": "Bases de Datos",
      "group": "A",
      "professor": "Perez",
      "meetings": [
        {"day": "Lunes", "start": "08:00", "end": "10:00"},
        {"day": "Miércoles", "start": "10:00", "end": "12:00"}
      ]
    },
    {
      "course": "Bases de Datos",
      "group": "B",
      "professor": "Gomez",
      "meetings": [
        {"day": "Martes", "start": "09:00", "end": "11:00"},
        {"day": "Jueves", "start": "14:00", "end": "16:00"}
      ]
    },
    {
      "course": "Redes",
      "group": "1",
      "professor": "Lopez",
      "meetings": [
        {"day": "Lunes", "start": "11:00", "end": "13:00"}
      ]
    }
  ],
  "constraints": {
    "no_afternoon": true,
    "exclude_days": ["Viernes"]
  },
  "max_per_day": 3,
  "top_n": 3
}

## 7) Variables de entorno esperadas
- LLM_API_KEY
- LLM_MODEL (opcional, default gemini-2.5-flash)
- LLM_SYSTEM_PROMPT (opcional)
- ELEVENLABS_API_KEY
- TTS_OUTPUT_FORMAT (opcional, default mp3_44100_128)
- TTS_STREAM_MODEL (opcional, default eleven_flash_v2_5)

Nota: Si TTS stream no esta disponible por plan/cuenta, el backend degrada automaticamente a batch cuando se usa modo auto o stream.

## 8) Consideraciones de latencia
- STT cliente reduce latencia total percibida en backend.
- Realtime TTS mejora tiempo a primer audio.
- El mayor costo suele venir de LLM + TTS, no del transporte HTTP.
- El endpoint /agent/text-only sirve para aislar y medir la latencia del pipeline sin audio.

## 9) Consideraciones de escalabilidad
- Memoria actual en proceso (RAM). Para escalado horizontal se recomienda persistencia externa por user_id/session_id.
- ActionModule esta desacoplado y listo para extender restricciones y ranking.
- TTSModule ya separa modo stream y batch, lo que simplifica politicas de degradacion.

## 10) Ejecucion local
1. Instalar dependencias del proyecto.
2. Definir variables de entorno en config.env o .env.
3. Levantar FastAPI con uvicorn apuntando a integration_module:app.
4. Probar endpoints con cliente HTTP (Postman, Insomnia o curl).

## 11) Prueba local sin Unity con `main.py`
`main.py` funciona como runner de consola para probar solo la generacion de horarios.

### Entrada esperada
Debe recibir un JSON con esta estructura:
```json
{
  "courses": [
    {
      "course": "Bases de Datos",
      "group": "A",
      "professor": "Perez",
      "meetings": [
        {"day": "Lunes", "start": "08:00", "end": "10:00"},
        {"day": "Miércoles", "start": "10:00", "end": "12:00"}
      ]
    }
  ],
  "constraints": {
    "hard": {},
    "soft": {},
    "weights": {}
  },
  "max_per_day": 3,
  "top_n": 3
}
```

## 12) Prueba local solo de interpretacion con `main_llm.py`
`main_llm.py` sirve para conversar con el LLM y revisar el JSON estructurado que interpreta antes de pasar por `ActionModule`.

### Entrada esperada
Puede recibir texto por argumento o por stdin:
```bash
python main_llm.py "Quiero un horario sin clases en la tarde"
python main_llm.py < prompt.txt
```

### Comportamiento
- Usa `input.json` como plantilla base si existe; si no, cae a una plantilla vacia.
- Le pide al LLM que devuelva solo un JSON con el mismo esquema que usan los `test_*.json`.
- Escribe el resultado en `output.json` por defecto para que puedas compararlo directamente.

### Plantilla alternativa
Si quieres probar contra otro archivo de referencia:
```bash
python main_llm.py --template test_1.json --output output.json "Solo quiero horarios de mañana"
```

### Salida esperada
`output.json` debe contener un JSON estructurado con esta forma general:
```json
{
  "courses": [...],
  "constraints": {
    "hard": [...],
    "soft": [...],
    "optimization": { "objectives": [...] },
    "scoring": { "mode": "fixed", "per": 30 }
  },
  "max_per_day": 3,
  "top_n": 3
}
```

## Nuevo esquema canónico de `constraints` (DSL)

Se introdujo un formato canónico y minimalista para expresar restricciones duras, preferencias blandas y objetivos de optimización.

Estructura principal:

```json
"constraints": {
  "hard": [ /* lista de reglas hard */ ],
  "soft": [ /* lista de reglas soft */ ],
  "optimization": { "primary": "maximize_courses", "secondary": ["minimize_days"] }
}
```

Regla (ejemplo de campos admitidos):

```json
{
  "id": "max_one_artistic",
  "type": "tag",            // tipo de predicado (time_window, count, tag, ...)
  "scope": "schedule",      // "meeting" | "schedule" | "course"
  "operator": "<=",        // operador aplicable (<=, >=, between, outside, etc.)
  "target": "artistic",     // objetivo del predicado (tag name, metric name)
  "value": 1,
  "reason": "Máx 1 curso artístico"
}
```

Campos habituales por tipo de regla:
- `time_window` (meeting): `range:{start:"HH:MM", end:"HH:MM"}` y `operator` puede ser `between` o `outside`.
- `count` (schedule): `target` puede ser `courses_per_day` u otras métricas, `operator` `<=|>=|==`, `value` numérico.
- `tag` (schedule): limita número de cursos con una `tag` concreta.

Principios importantes:
- Las reglas en `hard` se usan para podar combinaciones inviables antes del scoring.
- Las reglas en `soft` se traducen a bonificaciones/penalizaciones aplicadas al score final.
- `optimization.primary` define la métrica principal (p.ej. `maximize_courses`), y `secondary` lista objetivos lexicográficos.
- El motor ya no mantiene compatibilidad legacy; use el formato canónico para nuevas entradas.

Ejemplos rápidos
- Evitar tardes (no clases después de 12:00) — hard meeting rule:

```json
"hard": [
  { "type": "time_window", "scope": "meeting", "operator": "outside", "range": { "start": "12:00", "end": "23:59" }, "reason": "No tardes" }
]
```

- Un curso artístico máximo (hard schedule tag limit):

```json
"hard": [
  { "type": "tag", "scope": "schedule", "operator": "<=", "target": "artistic", "value": 1 }
]
```

- Preferir mañanas (soft meeting preference):

```json
"soft": [
  { "id": "pref_morning", "type": "time_window", "scope": "meeting", "operator": "between", "range": { "start": "07:00", "end": "12:00" }, "weight": 1 }
]
```

- Optimización: priorizar número de cursos distintos, luego minimizar días:

```json
"optimization": { "primary": "maximize_courses", "secondary": ["minimize_days"] }
```

Uso en `main.py` / endpoint `/schedule/test` (payload mínimo):

```json
{
  "courses": [ /* ... */ ],
  "constraints": {
    "hard": [],
    "soft": [],
    "optimization": { "primary": "maximize_courses" }
  },
  "max_per_day": 3,
  "top_n": 5
}
```

Notas para migración rápida desde fixtures legacy:
- Reemplace `no_afternoon` con una `time_window` hard `outside` a partir de `12:00`.
- Reemplace `single_course_per_day` con una regla `count` schedule `courses_per_day <= 1`.
- Reemplace `exclusive_tag_limits` con reglas `tag` en `hard`.

Si quieres, puedo añadir la sección de migración automática (script) que convierta los fixtures legacy a este formato.

**Detalles avanzados (optimización, métricas y scoring)**

Objetivos (nuevo formato): `optimization.objectives` es una lista de objetos con campos obligatorios `operator`, `target` y `priority`, y opcionales `weight` y `reason`. Se ordenan por `priority` (1 = mayor prioridad) y se evalúan en ese orden.

Ejemplo:

```json
"optimization": {
  "objectives": [
    { "operator": "maximize", "target": "distinct_courses", "priority": 1, "weight": 1 },
    { "operator": "minimize", "target": "days_on_campus", "priority": 2, "weight": 1 },
    { "operator": "minimize", "target": "total_gap_minutes", "priority": 3, "weight": 1 }
  ]
}
```

Notas:
- El motor ya no interpreta strings especiales (p.ej. `maximize_courses`). Use objetos explícitos.
- El `target` debe ser una métrica conocida (ver lista abajo) o `custom` si aplica una evaluación externa.

Métricas conocidas (`KNOWN_METRICS`):

- `distinct_courses`
- `days_on_campus`
- `total_gap_minutes`
- `morning_classes`
- `selected_sections`
- `courses_per_day`
- `meetings_per_day`
- `gaps_by_day`

Reglas de tipo `metric` (reemplaza `count`/`gap`):

```json
{
  "type": "metric",
  "scope": "schedule",
  "target": "courses_per_day",
  "operator": "<=",
  "value": 1
}
```

Scoring (soft rules):
- `scoring` es un objeto opcional en top-level con `mode` y `per`.
- `mode`: `fixed` (por defecto) o `linear`.
- `per`: unidad (minutos u otra métrica) usada por el modo `linear`.

Ejemplos:
- Penalización lineal por `total_gap_minutes` cada 30 minutos con peso 2:

```json
"scoring": { "mode": "linear", "per": 30 },
"soft": [
  { "type": "metric", "target": "total_gap_minutes", "operator": "avoid", "weight": 2 }
]
```

Explicación: si `total_gap_minutes == 120`, `per == 30`, `weight == 2`, la penalización aproximada será `-(120/30)*2 = -8`.

Validación y errores:
- El normalizador valida que `optimization.objectives[].target` sea una métrica conocida (a menos que sea `custom`).
- Se rechazan claves top-level inesperadas; use solo `hard`, `soft`, `optimization` y `scoring`.

Si quieres, genero ejemplos adicionales para `soft` basados en `metric` (p. ej. limitar gaps por día, preferir mañanas con scoring linear) o agrego tests unitarios para estos escenarios.

# Agente Virtual para Planificacion de Horarios

## Resumen
Este proyecto implementa un agente virtual corporizado para ayudar a construir y generar horarios academicos personalizados.

El sistema tiene dos partes principales:
- `unity-app/`: interfaz en Unity con avatar, audio, animaciones y canvas de horarios.
- `backend/`: API en Python/FastAPI que interpreta mensajes, mantiene estado conversacional y genera horarios de forma determinista.

La arquitectura actual no le pide al LLM que invente horarios finales. El LLM interpreta la conversacion y construye un `draft` estructurado; luego el motor determinista valida restricciones y genera los horarios.

## Demo
Enlace al demo:
- [Chippy - Agente de Generación de horarios](https://www.youtube.com/watch?v=OS5VJIIhZRk)

## Inicio rapido
Para correr el proyecto de forma local:

1. Crea un entorno virtual para el backend:

```bash
cd backend
py -m venv .venv
```

2. Activa el entorno virtual:

En PowerShell:

```bash
.\.venv\Scripts\Activate.ps1
```

En `cmd`:

```bash
.\.venv\Scripts\activate.bat
```

3. Instala las dependencias necesarias del backend:

```bash
python -m pip install fastapi uvicorn python-dotenv google-genai elevenlabs python-multipart
```

4. Agrega las API keys de Gemini y ElevenLabs en `backend/config.env`.
5. Si quieres verificar primero que el flujo textual con el LLM funciona sin Unity ni STT/TTS, corre:

```bash
cd backend
.\.venv\Scripts\python.exe test_text.py
```

Esto abre una prueba interactiva por consola. Escribe mensajes como:

```text
humanidades con Marta grupo 1, lunes de 7 a 8
```

Si todo esta bien, el script devolvera un payload estructurado con campos como `text`, `state` y, cuando corresponda, `schedule_report`.

6. Levanta el backend desde la carpeta `backend/` con:

```bash
py -m uvicorn integration_module:app --host 127.0.0.1 --port 8000
```

7. Abre el proyecto de Unity en `unity-app/`.
8. Carga la escena `Test_Map`.
9. Presiona `Play` en Unity.
10. Usa el boton del microfono para interactuar:
- presiona una vez para empezar a grabar,
- presiona de nuevo para detener y enviar el audio al backend.

Durante la interaccion:
- el boton `Horario` muestra la grilla del horario generado,
- el boton `Cursos` muestra los cursos que el agente tomo en cuenta,
- el boton `Restricciones` muestra las restricciones y preferencias activas.

Estos botones sirven para guiar a la persona usuaria mientras conversa con el agente y construye o genera su horario.

## Como funciona
Flujo general:
1. Unity envia texto o audio al backend.
2. Si entra audio, el backend transcribe con STT.
3. El backend decide el `workflow`:
- `chat`: respuesta conversacional simple.
- `schedule`: construccion de borrador de cursos y restricciones.
4. En `schedule`, el LLM devuelve un estado estructurado con:
- `assistant_message`
- `draft.courses`
- `draft.constraints`
- `status`
- `should_generate`
5. El backend valida el contrato del borrador.
6. Si el usuario confirma generar y el contrato es valido, el `ActionModule` arma y rankea horarios.
7. Unity recibe:
- `state` / `state_json`
- `schedule_report` / `schedule_json`
- `emotion_profile`
- `audio_base64`

## Arquitectura actual
### Unity
Scripts principales en `unity-app/Assets/Scripts/`:
- `AgentMicRecorder.cs`: graba audio y envia `/transcribe`.
- `AgentBackendReceiver.cs`: recibe la respuesta del backend y la reparte a avatar, audio y canvas.
- `ScheduleGridCanvas.cs`: renderiza horario, cursos considerados y restricciones.
- `AvatarEmotionDriver.cs`: aplica perfiles de animacion y blendshapes.
- `AgentAudioPlayer.cs`: reproduce TTS devuelto por el backend.

Tambien se usan animaciones como:
- `Idle`
- `Thinking`
- `Sad`
- `Surprise`
- `Victory`
- `PointLU`
- `PointRU`

### Backend
Modulos principales en `backend/`:
- `integration_module.py`: expone endpoints HTTP y orquesta servicios.
- `schedule_service.py`: flujo de construccion y generacion de horarios.
- `chat_service.py`: flujo conversacional general.
- `audio_service.py`: TTS/STT y respuesta realtime.
- `llm_module.py`: prompts y llamadas al LLM.
- `action_module.py`: generacion determinista de combinaciones de horario.
- `constraints_schema.py`: contrato y normalizacion del DSL de restricciones.
- `constraints_eval.py`: evaluacion de reglas hard/soft.
- `constraints_score.py`: ranking de horarios.
- `output_module.py`: shape final de respuesta para Unity.
- `test_text.py`: harness textual sin STT/TTS para probar exactamente el flujo del backend.

## Endpoints reales
### `POST /agent`
Entrada textual directa.

Request:
```json
{
  "content": "quiero llevar Humanidades con Marta",
  "user_id": "user1",
  "session_id": "default",
  "tts_mode": "batch",
  "workflow": "schedule"
}
```

Respuesta:
- `text`
- `audio_base64`
- `emotion_profile`
- `warnings`
- `state`
- `state_json`
- `schedule_report`
- `schedule_json`
- `output_json`

### `POST /transcribe`
Entrada de audio multipart.

Campos:
- `file`
- `user_id`
- `session_id`
- `tts_mode`
- `workflow`

Hace:
1. transcripcion STT
2. mismo flujo interno que `/agent`

### `POST /agent/realtime`
Entrega audio en stream NDJSON.

Eventos:
- `meta`
- `audio_chunk`
- `warning`
- `done`

## Flujo de horarios
El flujo de horarios sigue esta politica:
- el LLM interpreta cursos, grupos, profesores, reuniones y restricciones;
- el backend bloquea generacion si el `draft` rompe el contrato;
- `hard` filtra combinaciones inviables;
- el ranking determinista prioriza siempre `distinct_courses`;
- luego usa objetivos secundarios como `days_on_campus`;
- Unity renderiza:
  - horario generado
  - cursos considerados
  - restricciones activas

## Contrato del draft
El `workflow=schedule` espera que el LLM construya un estado con esta forma general:

```json
{
  "assistant_message": "texto breve",
  "draft": {
    "courses": [],
    "constraints": {
      "hard": [],
      "soft": [],
      "optimization": {
        "objectives": []
      },
      "scoring": {
        "mode": "fixed",
        "per": 30
      }
    }
  },
  "status": "collecting",
  "missing_items": [],
  "should_generate": false
}
```

Restricciones canonicas:
- top-level permitido: `hard`, `soft`, `optimization`, `scoring`
- `optimization.objectives[].operator`: solo `maximize` o `minimize`
- dias en espanol: `Lunes` a `Domingo`
- grupos en formato `Grupo N`
- horarios en formato `HH:MM`

## Politica de generacion
El sistema no usa al LLM como scheduler final.

En su lugar:
- el LLM estructura el problema;
- el backend valida el contrato;
- `ActionModule` genera combinaciones;
- se rankean por cobertura de cursos y luego por preferencias.

Esto hace que el resultado sea mas estable, testeable y consistente para produccion.

## Pruebas
### Harness textual
`backend/test_text.py` permite probar el flujo real sin STT/TTS:

```bash
cd backend
.\.venv\Scripts\python.exe test_text.py
```

Uso recomendado:
- primero agrega uno o mas cursos por texto;
- luego añade restricciones o preferencias;
- finalmente confirma generacion para verificar que el backend devuelva `schedule_report`.

### Suite de tests
```bash
cd backend
.\.venv\Scripts\python.exe -m pytest tests -q
```

La suite cubre:
- contrato de restricciones
- ranking determinista
- flujo schedule
- endpoints
- casos text-like e2e

## Variables de entorno
Archivo local:
- `backend/config.env`

Variables relevantes:
- `LLM_API_KEY`
- `LLM_MODEL`
- `LLM_EMOTION_PROFILES`
- `ELEVENLABS_API_KEY`
- `STT_MODEL_ID`
- `TTS_MODEL_ID`
- `TTS_VOICE_ID`
- `BACKEND_DEBUG_LOGS`
- `LLM_RETRIES`
- `LLM_RETRY_DELAY`
- `STT_RETRIES`
- `STT_RETRY_DELAY`
- `TTS_RETRIES`
- `TTS_RETRY_DELAY`

## Estructura del repositorio
```text
.
|-- README.md
|-- .gitignore
|-- backend/
|   |-- integration_module.py
|   |-- schedule_service.py
|   |-- chat_service.py
|   |-- audio_service.py
|   |-- llm_module.py
|   |-- action_module.py
|   |-- constraints_schema.py
|   |-- constraints_eval.py
|   |-- constraints_score.py
|   |-- output_module.py
|   |-- test_text.py
|   `-- tests/
`-- unity-app/
    |-- Assets/
    |   |-- Scripts/
    |   |-- Animations/
    |   `-- Scenes/
    |-- Packages/
    `-- ProjectSettings/
```

## Estado actual
Actualmente el proyecto ya soporta:
- conversacion por audio y por texto
- borrador estructurado de cursos y restricciones
- generacion determinista de horarios
- salida estructurada para Unity
- perfiles de animacion conversacionales y de apuntar (`point_lu`, `point_ru`)

Pendientes tipicos de producto:
- endurecer aun mas integracion Unity/backend
- validar visualmente todos los casos del `ScheduleGridCanvas`
- agregar demo publico en la seccion correspondiente

# llm_module.py
import json
import os
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from google import genai

load_dotenv("config.env", override=False)
load_dotenv()


class LLMModule:
    """
    Conversational Core para un agente virtual.
    Configurable via variables de entorno para poder cambiar de modelo sin tocar el codigo.
    """

    def __init__(self):
        self.api_key = os.getenv("LLM_API_KEY")
        if not self.api_key:
            raise ValueError("Falta LLM_API_KEY en el entorno")

        self.model = os.getenv("LLM_MODEL") or "gemini-2.5-flash"

        self.system_prompt = os.getenv("LLM_SYSTEM_PROMPT") or (
            "Eres un asistente virtual que responde de manera clara, breve y amigable. "
            "Responde solo con JSON valido y solo usa informacion real del usuario."
        )

        self.available_emotion_profiles = self._load_emotion_profiles_from_env()
        self.client = genai.Client(api_key=self.api_key, vertexai=False)
        self.history = []

    def _friendly_fallback_response(self) -> str:
        return "Algo salio mal, puedes repetirlo?"

    def _load_emotion_profiles_from_env(self) -> List[str]:
        raw_profiles = os.getenv("LLM_EMOTION_PROFILES", "neutral,friendly,thinking,sad,surprise,happy")
        profiles = [profile.strip() for profile in raw_profiles.split(",") if profile.strip()]
        return profiles or ["neutral"]

    def build_agent_response_prompt(self, available_profiles: Optional[List[str]] = None) -> str:
        profiles = available_profiles or self.available_emotion_profiles
        profiles_text = ", ".join(profiles)
        default_profile = profiles[0] if profiles else "neutral"

        return (
            "Tu nombre es Chippy. Eres un asistente conversacional para un avatar en Unity. "
            "Debes responder siempre con JSON valido y nada mas. "
            "Manten tus respuestas cortas. "
            "No respondas a nada que no este relacionado con horarios; si el usuario pregunta otra cosa, redirige brevemente al tema de horarios. "
            "Tu salida debe usar exactamente estas keys: text y emotion_profile. "
            "emotion_profile debe ser siempre uno de los perfiles permitidos. "
            "No pidas doble confirmacion para crear el horario: detecta el intento del usuario y genera el horario cuando lo pida explicitamente, o bien ofrecelo luego de haber agregado cursos si todavia falta confirmacion. "
            "Antes de generar el horario, no repitas todos los cursos agregados; en su lugar, indicale que puede ver los cursos considerados y las restricciones usando los botones de la esquina superior izquierda de la pantalla. "
            "Cuando el horario quede listo, NO enumeres cursos, grupos, profesores ni restricciones: solo dile que ya esta listo y que puede ver el horario en la esquina superior derecha de la pantalla. "
            "Los cursos que aparecen como referencia o ejemplo son solo para interpretacion interna del LLM; no los repitas ni los presentes como parte de la respuesta final. "
            "Nunca inventes perfiles fuera de la lista. "
            "Siempre debes especificar un emotion_profile.\n\n"
            f"Perfiles permitidos: {profiles_text}\n\n"
            "Formato esperado de salida:\n"
            "{\n"
            '  "text": "respuesta breve para el usuario",\n'
            f'  "emotion_profile": "{default_profile}"\n'
            "}\n\n"
            "Reglas: responde solo con JSON valido y usa un solo emotion_profile por respuesta."
        )

    def _build_contents(
        self,
        user_text: str,
        history: Optional[List[Dict]] = None,
        system_prompt: Optional[str] = None,
    ) -> List[Dict]:
        contents = [{"role": "user", "parts": [{"text": system_prompt or self.system_prompt}]}]

        for msg in history or []:
            role = "model" if msg["role"] == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})

        contents.append({"role": "user", "parts": [{"text": user_text}]})
        return contents

    def _generate_text(
        self,
        prompt_text: str,
        history: Optional[List[Dict]] = None,
        system_prompt: Optional[str] = None,
        store_user_text: Optional[str] = None,
    ) -> str:
        contents = self._build_contents(prompt_text, history or self.history, system_prompt=system_prompt)

        last_error = None
        for _ in range(3):
            try:
                response = self.client.models.generate_content(model=self.model, contents=contents)
                response_text = response.text.strip()
                if store_user_text is not None:
                    self.add_to_history("user", store_user_text)
                    self.add_to_history("assistant", response_text)
                return response_text
            except Exception as e:
                last_error = e

        raise RuntimeError("LLM unavailable after retries") from last_error

    def add_to_history(self, role: str, content: str):
        self.history.append({"role": role, "content": content})

    def generate_response(
        self,
        user_text: str,
        history: Optional[List[Dict]] = None,
        system_prompt: Optional[str] = None,
    ) -> str:
        return self._generate_text(
            user_text,
            history=history or self.history,
            system_prompt=system_prompt,
            store_user_text=user_text,
        )

    def build_schedule_chat_prompt(
        self,
        user_text: str,
        current_draft: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict]] = None,
    ) -> str:
        draft_json = json.dumps(
            current_draft
            or {
                "courses": [],
                "constraints": {
                    "hard": [],
                    "soft": [],
                    "optimization": {"objectives": []},
                    "scoring": {"mode": "fixed", "per": 30},
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        history_json = json.dumps(history or [], ensure_ascii=False, indent=2)

        return (
            "Tu nombre es Chippy. Eres un asistente para construir paso a paso el borrador de horarios. "
            "Responde solo con JSON valido. Sin markdown. Sin texto extra. "
            "No llames a ActionModule ni inventes horarios finales.\n\n"
            "FORMATO DE SALIDA OBLIGATORIO (sin keys extra):\n"
            "{\n"
            '  "assistant_message": "texto breve",\n'
            '  "draft": {"courses": [], "constraints": {"hard": [], "soft": [], "optimization": {"objectives": []}, "scoring": {"mode": "fixed", "per": 30}}},\n'
            '  "status": "collecting" | "awaiting_confirmation",\n'
            '  "missing_items": [],\n'
            '  "emotion_profile": "neutral",\n'
            '  "should_generate": false\n'
            "}\n\n"
            "CONTRATO CANONICO OBLIGATORIO (constraints.py):\n"
            "- constraints solo puede tener: hard, soft, optimization, scoring.\n"
            "- optimization solo puede tener: objectives.\n"
            "- Operadores permitidos: include, exclude, prefer, avoid, <=, >=, ==, between, outside.\n"
            "- NO usar: not_in, in, equals, gt, lt, neq.\n"
            "- Types permitidos: day, time_window, professor, group, course, metric, tag, campus, custom.\n"
            "- Scopes permitidos: meeting, course, schedule, day.\n"
            "- Regla hard/soft siempre incluye type y operator.\n"
            "- Campos permitidos por regla: type, scope, operator, reason, target, value, days, range, values, weight, aggregation.\n"
            "- day usa days (array no vacio) con: Lunes, Martes, Miercoles, Jueves, Viernes, Sabado, Domingo.\n"
            "- NO usar dias en ingles: MONDAY, FRIDAY, etc.\n"
            "- time_window usa range.start y range.end en HH:MM.\n"
            "- professor/group/course/campus usan values (array no vacio), no target.\n"
            "- metric requiere target. Si operator es <=, >= o ==, requiere value numerico.\n"
            "- aggregation permitida: sum, max, min, count.\n"
            "- optimization.objectives: objetos con operator, target, priority; opcionales weight, reason, aggregation.\n"
            "- En optimization.objectives, operator SOLO puede ser: maximize o minimize. No usar min/max.\n"
            "- targets metric/optimization conocidos: distinct_courses, days_on_campus, total_gap_minutes, morning_classes, selected_sections, courses_per_day, meetings_per_day, gaps_by_day.\n\n"
            "- No inventes keys nuevas en ningun nivel. Si falta un dato, pregunta; no improvises campos.\n"
            "REGLAS DE DRAFT:\n"
            "- Mantener y actualizar draft; no resetear salvo que el usuario lo pida.\n"
            "- Cada item en courses es seccion/grupo alternativo.\n"
            "- Cada curso usa: course, group, professor, meetings.\n"
            "- Cada meeting usa: day, start, end.\n"
            "- Formato de professor: Nombre o Nombre Apellido. El apellido no es obligatorio; si aparece, cada palabra debe iniciar con mayuscula (ejemplos: Juan, Juan Perez).\n"
            "- Formato obligatorio de course: Capitaliza cada palabra (ejemplo: Calculo Integral).\n"
            "- Formato obligatorio de day: Lunes, Martes, Miercoles, Jueves, Viernes, Sabado, Domingo.\n"
            "- Formato obligatorio de group: 'Grupo N' (ejemplo: Grupo 1). No usar G1, g1, 1, A, B.\n"
            "- Horas en HH:MM (24h).\n"
            "- Si falta professor: usa 'Desconocido' o pide aclaracion breve.\n"
            "- Si falta informacion clave, preguntar solo por lo faltante.\n"
            "- No inventar max_per_day/top_n si no lo pide el usuario.\n\n"
            "- Si el usuario expresa preferencias ambiguas (poco, mucho, etc.), no las traduzcas a un numero duro automaticamente.\n"
            "- Para ambiguedad: propone una suposicion conservadora en assistant_message y pregunta si confirma.\n"
            "- Mientras no haya confirmacion, deja la preferencia en optimization/soft, no en hard estricta.\n"
            "- Ejemplo recomendado: 'ir pocos dias' -> optimization minimize days_on_campus, sin imponer hard == 1.\n"
            "- Solo crea hard metric con value numerico cuando el usuario lo diga explicitamente o lo confirme.\n"
            "- Recuerda la jerarquia: hard > soft > optimization. No conviertas una preferencia vaga en hard.\n\n"
            "REGLAS DE COHERENCIA:\n"
            "- should_generate=true SOLO si el usuario confirma explicitamente generar.\n"
            "- Si should_generate=false, assistant_message NO puede decir que el horario ya fue generado.\n"
            "- Si should_generate=true, status debe ser awaiting_confirmation o equivalente a ejecucion inmediata.\n"
            "- Si aun faltan datos, usar status=collecting.\n\n"
            "EMOCION:\n"
            "- emotion_profile obligatorio y debe ser uno de: " + ", ".join(self.available_emotion_profiles) + ".\n\n"
            f"Historial reciente:\n{history_json}\n\n"
            f"Borrador actual:\n{draft_json}\n\n"
            f"Mensaje del usuario:\n{user_text}"
        )

    def generate_schedule_chat_turn(
        self,
        user_text: str,
        current_draft: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict]] = None,
    ) -> str:
        prompt = self.build_schedule_chat_prompt(user_text, current_draft=current_draft, history=history)
        return self._generate_text(prompt, history=history or self.history, store_user_text=user_text)

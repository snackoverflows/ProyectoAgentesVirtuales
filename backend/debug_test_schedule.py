import json
from integration_module import _build_schedule_report

payload = {
  "assistant_message": "¡De acuerdo! Procederé a generar tus horarios con la información proporcionada.",
  "draft": {
    "courses": [
      {
        "course_id": "bases de datos",
        "section_id": "Rodolfo",
        "instructor": "Rodolfo",
        "meetings": [
          {"day": "Jueves", "start_time": "15:00", "end_time": "17:00"}
        ]
      },
      {
        "course_id": "bases de datos",
        "section_id": "Miriam",
        "instructor": "Miriam",
        "meetings": [
          {"day": "Jueves", "start_time": "18:00", "end_time": "19:00"}
        ]
      },
      {
        "course_id": "bases de datos",
        "section_id": "Jose Perez",
        "instructor": "Jose Perez",
        "meetings": [
          {"day": "Viernes", "start_time": "07:00", "end_time": "09:00"}
        ]
      },
      {
        "course_id": "humanidades",
        "section_id": "Rocio",
        "instructor": "Rocio",
        "meetings": [
          {"day": "Lunes", "start_time": "06:00", "end_time": "09:00"},
          {"day": "Jueves", "start_time": "06:00", "end_time": "09:00"}
        ]
      },
      {
        "course_id": "humanidades",
        "section_id": "Luis",
        "instructor": "Luis",
        "meetings": [
          {"day": "Lunes", "start_time": "09:00", "end_time": "12:00"},
          {"day": "Jueves", "start_time": "09:00", "end_time": "12:00"}
        ]
      }
    ],
    "constraints": {
      "hard": [],
      "soft": [
        {
          "type": "time_window",
          "time_window": {"start_time": "14:00", "end_time": "23:00"},
          "preference_level": "avoid"
        }
      ],
      "optimization": {"objectives": []},
      "scoring": {"mode": "fixed", "per": 30}
    }
  },
  "status": "awaiting_confirmation",
  "missing_items": [],
  "should_generate": True
}

# The _build_schedule_report expects the payload at top-level with courses/constraints
report = _build_schedule_report(payload.get('draft', payload))
print(json.dumps(report, ensure_ascii=False, indent=2))

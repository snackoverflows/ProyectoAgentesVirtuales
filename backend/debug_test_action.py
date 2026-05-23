import json
from action_module import ActionModule

sample_draft = {
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
}

# normalization (same logic applied in integration_module)
normalized_courses = []
for section in sample_draft.get('courses', []):
    course_name = section.get('course') or section.get('course_id') or section.get('course_name')
    group = section.get('group') or section.get('section') or section.get('section_id')
    professor = section.get('professor') or section.get('instructor')

    meetings = section.get('meetings') or section.get('options') or []
    normalized_meetings = []
    for m in meetings:
        day = m.get('day') or m.get('weekday')
        start = m.get('start') or m.get('start_time') or m.get('inicio')
        end = m.get('end') or m.get('end_time') or m.get('fin')
        meeting = {}
        if day is not None:
            meeting['day'] = day
        if start is not None:
            meeting['start'] = start
        if end is not None:
            meeting['end'] = end
        normalized_meetings.append(meeting)

    normalized_courses.append({
        'course': course_name or 'Curso sin nombre',
        'group': group or 'sin-grupo',
        'professor': professor or 'Indefinido',
        'meetings': normalized_meetings,
    })

am = ActionModule()
# call get_best_schedules
schedules = am.get_best_schedules(normalized_courses, sample_draft.get('constraints', {}), max_per_day=None, top_n=5)

print(json.dumps({'n_schedules': len(schedules), 'schedules_preview': schedules[:2]}, ensure_ascii=False, indent=2))

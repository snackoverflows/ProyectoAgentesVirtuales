# action_module.py
from typing import Any, List, Dict, Optional
import constraints as constraints_module

class ActionModule:
    """
    Módulo para generar y validar horarios optimizados.
    """

    def __init__(self):
        pass

    def _time_to_minutes(self, time_value: str) -> int:
        hours, minutes = time_value.split(":")
        return int(hours) * 60 + int(minutes)

    def _blocks_overlap(self, left: Dict, right: Dict) -> bool:
        if left["day"] != right["day"]:
            return False

        left_start = self._time_to_minutes(left["start"])
        left_end = self._time_to_minutes(left["end"])
        right_start = self._time_to_minutes(right["start"])
        right_end = self._time_to_minutes(right["end"])

        return left_start < right_end and right_start < left_end

    def _normalize_section(self, section: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normaliza una seccion/grupo de curso.

        Contrato recomendado:
        {
            "course": "Bases de Datos",
            "group": "A",
            "professor": "Perez",
            "meetings": [
                {"day": "Lunes", "start": "08:00", "end": "10:00"},
                {"day": "Miércoles", "start": "10:00", "end": "12:00"}
            ]
        }

        Compatibilidad:
        - Si llega "options", se interpreta como alias de "meetings".
        - Si no llega "group", se asigna un identificador estable.
        """
        normalized = section.copy()
        normalized["course"] = normalized.get("course", "Curso sin nombre")
        normalized["group"] = normalized.get("group") or normalized.get("section") or "sin-grupo"
        normalized["professor"] = normalized.get("professor", "Indefinido")
        normalized["tags"] = normalized.get("tags", []) if isinstance(normalized.get("tags", []), list) else []

        meetings = normalized.get("meetings")
        if meetings is None:
            meetings = normalized.get("options", [])

        normalized["meetings"] = [meeting.copy() for meeting in meetings]
        for meeting in normalized["meetings"]:
            meeting["course"] = normalized["course"]
            meeting["group"] = normalized["group"]
            if "professor" not in meeting:
                meeting["professor"] = normalized["professor"]
            meeting["tags"] = list(normalized.get("tags", []))

        return normalized

    def _count_distinct_courses(self, schedule: List[Dict[str, Any]]) -> int:
        return len({block.get("course") for block in schedule if block.get("course")})

    def _group_sections_by_course_name(self, courses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Agrupa secciones por nombre de curso, manteniendolas como alternativas.

        Cada elemento de `courses` representa una seccion/grupo. Si hay varias
        entradas con el mismo `course`, el generador elegira solo una de esas
        secciones para el horario final.
        """
        grouped: Dict[str, Dict[str, Any]] = {}

        for section in courses:
            normalized_section = self._normalize_section(section)
            course_name = normalized_section["course"]

            if course_name not in grouped:
                grouped[course_name] = {
                    "course": course_name,
                    "sections": [],
                }

            grouped[course_name]["sections"].append(normalized_section)

        return list(grouped.values())

    def generate_all_schedules(
        self,
        courses: List[Dict[str, Any]],
        constraints: Dict[str, Any],
        max_per_day: Optional[int] = 3,
    ) -> List[List[Dict[str, Any]]]:
        """
        Genera combinaciones válidas respetando overlaps, hard constraints y el
        máximo de meetings por día.
        """
        normalized_for_checks = constraints_module.normalize_constraints(constraints)
        max_meetings_per_day = float("inf") if max_per_day is None else max_per_day

        normalized_courses = self._group_sections_by_course_name(courses)

        sections_per_course = []
        for course in normalized_courses:
            valid_sections = []
            for section in course.get("sections", []):
                meetings = section.get("meetings", [])
                if not meetings:
                    continue

                normalized_meetings = []
                section_valid = True
                for meeting in meetings:
                    meeting_copy = meeting.copy()
                    meeting_copy["course"] = section["course"]
                    meeting_copy["group"] = section["group"]
                    meeting_copy["professor"] = section.get("professor", meeting_copy.get("professor", "Indefinido"))
                    if constraints_module.meeting_violates_hard(meeting_copy, normalized_for_checks):
                        section_valid = False
                        break
                    normalized_meetings.append(meeting_copy)

                if section_valid:
                    valid_sections.append({
                        "course": section["course"],
                        "group": section["group"],
                        "professor": section.get("professor", "Indefinido"),
                        "tags": section.get("tags", []),
                        "meetings": normalized_meetings,
                    })

            sections_per_course.append([None] + valid_sections)

        valid_schedules: List[List[Dict[str, Any]]] = []

        def rollback(added_blocks: int, partial_schedule: List[Dict[str, Any]], day_count: Dict[str, int]) -> None:
            for _ in range(added_blocks):
                removed_block = partial_schedule.pop()
                removed_day = removed_block["day"]
                day_count[removed_day] -= 1
                if day_count[removed_day] <= 0:
                    del day_count[removed_day]

        def backtrack(
            course_index: int,
            partial_schedule: List[Dict[str, Any]],
            day_count: Dict[str, int],
        ) -> None:
            if course_index == len(sections_per_course):
                valid_schedules.append(list(partial_schedule))
                return

            for section in sections_per_course[course_index]:
                if section is None:
                    backtrack(course_index + 1, partial_schedule, day_count)
                    continue

                added_blocks = 0
                section_valid = True

                for block in section.get("meetings", []):
                    day = block["day"]

                    if day_count.get(day, 0) >= max_meetings_per_day:
                        section_valid = False
                        break

                    if any(self._blocks_overlap(block, scheduled) for scheduled in partial_schedule):
                        section_valid = False
                        break

                    partial_schedule.append(block)
                    day_count[day] = day_count.get(day, 0) + 1
                    added_blocks += 1

                    if constraints_module.hard_violated(partial_schedule, normalized_for_checks):
                        section_valid = False
                        break

                if not section_valid:
                    rollback(added_blocks, partial_schedule, day_count)
                    continue

                backtrack(course_index + 1, partial_schedule, day_count)

                rollback(added_blocks, partial_schedule, day_count)

        backtrack(0, [], {})
        return valid_schedules

    def score_schedule(self, schedule: List[Dict[str, Any]], constraints: Dict[str, Any]) -> int:
        """
        Devuelve un puntaje para ordenar los horarios.
        La prioridad principal es maximizar la cantidad de cursos distintos
        incluidos en el horario. Las preferencias blandas solo resuelven empates.
        """
        normalized = constraints_module.normalize_constraints(constraints)

        rank_key = constraints_module.schedule_rank_key(schedule, normalized)
        score = constraints_module.rank_key_to_score(rank_key)

        return int(score)

    def get_best_schedules(
        self,
        courses: List[Dict[str, Any]],
        constraints: Dict[str, Any],
        max_per_day: Optional[int] = 3,
        top_n: int = 3,
    ) -> List[List[Dict[str, Any]]]:
        """
        Genera todas las combinaciones válidas y devuelve las top_n mejores según score.
        """
        all_valid = self.generate_all_schedules(courses, constraints, max_per_day)
        scored = [(self.score_schedule(s, constraints), s) for s in all_valid]
        scored.sort(key=lambda x: x[0], reverse=True)
        best = [s for score, s in scored[:top_n]]
        return best

    def validate_schedule(self, schedule: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """
        Detecta conflictos de horarios dentro de un horario dado.
        """
        warnings = []
        for index, block in enumerate(schedule):
            for other in schedule[index + 1 :]:
                if self._blocks_overlap(block, other):
                    warnings.append(
                        f"Conflicto: {block['course']} se traslapa con {other['course']}"
                    )
        return {"warnings": warnings}
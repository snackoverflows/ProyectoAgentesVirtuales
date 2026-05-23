import json
from action_module import ActionModule

import os

default_files = ['test.json', 'test_2.json', 'test_1.json', 'input.json']
found = None
for fn in default_files:
    if os.path.exists(fn):
        found = fn
        break

if not found:
    raise SystemExit('No test JSON found. Create test.json or test_2.json in workspace.')

with open(found, 'r', encoding='utf-8') as f:
    payload = json.load(f)

am = ActionModule()
all_valid = am.generate_all_schedules(payload.get('courses', []), payload.get('constraints', {}), max_per_day=int(payload.get('max_per_day', 3)))

scored = [(am.score_schedule(s, payload.get('constraints', {})), am._count_distinct_courses(s), len(s), s) for s in all_valid]
scored.sort(key=lambda x: x[0], reverse=True)

report = []
for score, distinct, length, schedule in scored:
    report.append({'score': score, 'distinct': distinct, 'length': length, 'schedule': schedule})

print(json.dumps(report, ensure_ascii=False, indent=2))

"""스케줄 저장 tool."""

import importlib


def _load_legacy_scheduler():
    try:
        return importlib.import_module("src.scheduler")
    except ModuleNotFoundError:
        return importlib.import_module("scheduler")


legacy_scheduler = _load_legacy_scheduler()


def clean_and_store(response):
    """응답에서 [SCHED:*] 태그를 제거하고 스케줄을 저장한다."""
    lines = response.split("\n")
    clean_lines = []
    actions = []

    for line in lines:
        match = legacy_scheduler.SCHED_PATTERN.match(line.strip())
        if not match:
            clean_lines.append(line)
            continue

        action = match.group(1)
        expression = match.group(2).strip()
        message = match.group(3).strip()

        if action == "cancel":
            try:
                legacy_scheduler.cancel_job(int(expression))
                actions.append({"action": action, "job_id": int(expression)})
            except ValueError:
                print(f"[tool.schedule] invalid cancel id: {expression}")
            continue

        job_id = legacy_scheduler.add_job(action, expression, message)
        if job_id is not None:
            actions.append(
                {
                    "action": action,
                    "job_id": job_id,
                    "expression": expression,
                    "message": message,
                }
            )

    return "\n".join(clean_lines).rstrip(), actions

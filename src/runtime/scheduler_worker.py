#!/usr/bin/env python3
"""런타임 기반 스케줄 워커.

만기된 스케줄을 조회하고 GPT 응답을 생성해 outbox로 적재한다.
bridge가 outbox를 iMessage로 전달한다.
"""

import argparse
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

try:
    import memory as legacy_memory
    import scheduler as legacy_scheduler
    from runtime.orchestrator import handle_scheduled_job
except ModuleNotFoundError:
    from src import memory as legacy_memory
    from src import scheduler as legacy_scheduler
    from src.runtime.orchestrator import handle_scheduled_job

load_dotenv()

from heartbeat import beat

RECIPIENT = os.environ["ALF_MY_NUMBER"]
POLL_INTERVAL = 2


def init_runtime():
    legacy_memory.init()
    legacy_scheduler.init(legacy_memory.DB_PATH)


def process_due_jobs():
    """현재 만기된 잡들을 처리한다."""
    due_jobs = legacy_scheduler.get_due_jobs()
    if not due_jobs:
        return 0

    processed = 0
    for job in due_jobs:
        print(f"[sched] 실행 #{job['id']}: {job['message'][:60]}")
        legacy_scheduler.mark_run(job["id"])
        try:
            handle_scheduled_job(job, RECIPIENT)
            processed += 1
        except Exception as exc:
            print(f"[sched] 처리 실패 #{job['id']}: {exc}")
    return processed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="만기 잡 1회만 처리")
    args = parser.parse_args()

    init_runtime()

    if args.once:
        count = process_due_jobs()
        print(f"[sched] processed={count}")
        return

    print(f"Scheduler 감시 시작 — recipient: {RECIPIENT}")
    beat("schedule", "ok", "시작됨")
    while True:
        try:
            n = process_due_jobs()
            beat("schedule", "ok" if n else "idle", f"처리 {n}건" if n else "대기 중")
        except KeyboardInterrupt:
            print("Scheduler 종료")
            break
        except Exception as exc:
            beat("schedule", "error", str(exc)[:100])
            print(f"[sched] loop error: {exc}")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()

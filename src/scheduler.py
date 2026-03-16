"""내장 스케줄러 — at/every/daily 잡 관리."""

import re
import sqlite3
from datetime import datetime, timedelta

# [SCHED:daily 08:00] 아침 브리핑 해줘
# [SCHED:at 2026-03-05 14:00] 팀 미팅 알림
# [SCHED:every 3600] 이메일 확인
# [SCHED:cancel 3]
SCHED_PATTERN = re.compile(
    r"\[SCHED:(daily|at|every|cancel)\s+(.+?)\]\s*(.*)"
)

_conn = None


def init(db_path):
    """스케줄 테이블 생성. memory.py와 같은 DB 사용."""
    global _conn
    _conn = sqlite3.connect(db_path)
    _conn.row_factory = sqlite3.Row
    _conn.executescript("""
        CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            expression TEXT NOT NULL,
            message TEXT NOT NULL,
            next_run TEXT NOT NULL,
            last_run TEXT,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );
    """)
    _conn.commit()


def add_job(job_type, expression, message):
    """잡 등록. next_run 자동 계산."""
    next_run = _calc_next_run(job_type, expression)
    if next_run is None:
        print(f"[sched] 잘못된 스케줄: {job_type} {expression}")
        return None

    cur = _conn.execute(
        "INSERT INTO schedules (type, expression, message, next_run) VALUES (?, ?, ?, ?)",
        (job_type, expression, message, next_run.isoformat()),
    )
    _conn.commit()
    job_id = cur.lastrowid
    print(f"[sched] 등록 #{job_id}: {job_type} {expression} → {next_run.strftime('%m/%d %H:%M')}")
    return job_id


def cancel_job(job_id):
    """잡 비활성화."""
    _conn.execute("UPDATE schedules SET enabled=0 WHERE id=?", (job_id,))
    _conn.commit()
    print(f"[sched] 취소 #{job_id}")


def get_due_jobs():
    """실행할 잡 목록 반환."""
    now = datetime.now().isoformat()
    rows = _conn.execute(
        "SELECT * FROM schedules WHERE enabled=1 AND next_run <= ?", (now,)
    ).fetchall()
    return [dict(r) for r in rows]


def mark_run(job_id):
    """실행 완료 처리. 반복 잡은 next_run 갱신, 일회성은 비활성화."""
    row = _conn.execute("SELECT * FROM schedules WHERE id=?", (job_id,)).fetchone()
    if not row:
        return

    now = datetime.now()

    if row["type"] == "at":
        # 일회성 → 비활성화
        _conn.execute(
            "UPDATE schedules SET last_run=?, enabled=0 WHERE id=?",
            (now.isoformat(), job_id),
        )
    else:
        # 반복 → next_run 갱신
        next_run = _calc_next_run(row["type"], row["expression"], after=now)
        _conn.execute(
            "UPDATE schedules SET last_run=?, next_run=? WHERE id=?",
            (now.isoformat(), next_run.isoformat(), job_id),
        )
    _conn.commit()


def get_active_jobs():
    """활성 잡 목록 (프롬프트 주입용)."""
    rows = _conn.execute(
        "SELECT id, type, expression, message, next_run FROM schedules WHERE enabled=1 "
        "ORDER BY next_run"
    ).fetchall()
    return [dict(r) for r in rows]


def parse_and_save(response):
    """응답에서 [SCHED:...] 파싱 → 잡 등록/취소 → 클린 응답 반환."""
    lines = response.split("\n")
    clean_lines = []

    for line in lines:
        match = SCHED_PATTERN.match(line.strip())
        if match:
            action, expr, message = match.group(1), match.group(2).strip(), match.group(3).strip()
            if action == "cancel":
                try:
                    cancel_job(int(expr))
                except ValueError:
                    pass
            else:
                add_job(action, expr, message)
        else:
            clean_lines.append(line)

    return "\n".join(clean_lines).rstrip()


def _calc_next_run(job_type, expression, after=None):
    """다음 실행 시각 계산."""
    now = after or datetime.now()

    if job_type == "at":
        # ISO 형식: "2026-03-05 14:00" 또는 "2026-03-05T14:00"
        try:
            target = datetime.fromisoformat(expression.replace(" ", "T"))
            return target if target > now else None
        except ValueError:
            return None

    elif job_type == "every":
        # 초 단위 간격
        try:
            seconds = int(expression)
            return now + timedelta(seconds=seconds)
        except ValueError:
            return None

    elif job_type == "daily":
        # "HH:MM" 형식
        try:
            hour, minute = map(int, expression.split(":"))
            target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if target <= now:
                target += timedelta(days=1)
            return target
        except (ValueError, AttributeError):
            return None

    return None

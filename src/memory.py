"""메모리 관리 — SQLite 기반 기억 저장/로딩.

1M 컨텍스트를 활용해 전체 메모리+히스토리를 로드한다.
별도 검색 인프라(FTS5, 벡터) 없이 LLM이 직접 시맨틱 매칭을 수행.
"""

import json
import os
import re
import sqlite3
import subprocess
from collections import defaultdict
from datetime import datetime

MEMORY_DIR = os.path.join(os.path.dirname(__file__), "..", "memory")
DB_PATH = os.path.join(MEMORY_DIR, "alf.db")

# [MEM:about] 내용, [MEM:calendar] 내용, [MEM:notes] 내용
MEM_PATTERN = re.compile(r"\[MEM:(\w+)\]\s*(.+)")

VALID_TYPES = {"about", "calendar", "notes"}

# compaction 설정
COMPACT_THRESHOLD = 500   # 이 건수 초과 시 compact 트리거
COMPACT_KEEP_RECENT = 50  # 최근 N건은 원문 유지
CLAUDE_CLI = "/Users/afred/.local/bin/claude"

_conn = None


def _get_conn():
    global _conn
    if _conn is None:
        os.makedirs(MEMORY_DIR, exist_ok=True)
        _conn = sqlite3.connect(DB_PATH)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
    return _conn


def init():
    """DB 스키마 생성 + 기존 .md/.jsonl 마이그레이션."""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_msg TEXT NOT NULL,
            alf_msg TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );
        CREATE INDEX IF NOT EXISTS idx_mem_type ON memories(type);
        CREATE INDEX IF NOT EXISTS idx_mem_created ON memories(created_at);
        CREATE INDEX IF NOT EXISTS idx_hist_created ON history(created_at);
    """)
    conn.commit()
    _migrate_legacy(conn)
    _cleanup_fts(conn)


def _cleanup_fts(conn):
    """불필요한 FTS5 테이블/트리거 정리 (레거시)."""
    for table in ["memories_fts", "history_fts"]:
        try:
            conn.execute(f"DROP TABLE IF EXISTS {table}")
        except sqlite3.OperationalError:
            pass
    for trigger in ["memories_ai", "memories_ad", "memories_au",
                     "history_ai", "history_ad"]:
        try:
            conn.execute(f"DROP TRIGGER IF EXISTS {trigger}")
        except sqlite3.OperationalError:
            pass
    conn.commit()


def _migrate_legacy(conn):
    """기존 .md 파일 → SQLite 1회 마이그레이션."""
    count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
    if count > 0:
        return

    migrated = 0
    for mem_type in VALID_TYPES:
        path = os.path.join(MEMORY_DIR, f"{mem_type}.md")
        if not os.path.exists(path):
            continue
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                content = line.lstrip("- ").strip()
                date_match = re.search(r"\((\d{4}-\d{2}-\d{2})\)$", content)
                if date_match:
                    created = date_match.group(1)
                    content = content[:date_match.start()].strip()
                else:
                    created = datetime.now().strftime("%Y-%m-%d")
                if content:
                    conn.execute(
                        "INSERT INTO memories (type, content, created_at) VALUES (?, ?, ?)",
                        (mem_type, content, created),
                    )
                    migrated += 1

    hist_path = os.path.join(MEMORY_DIR, "history.jsonl")
    if os.path.exists(hist_path):
        with open(hist_path) as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    conn.execute(
                        "INSERT INTO history (user_msg, alf_msg, created_at) VALUES (?, ?, ?)",
                        (entry["user"], entry["alf"], entry.get("ts", datetime.now().isoformat())),
                    )
                    migrated += 1
                except (json.JSONDecodeError, KeyError):
                    continue

    conn.commit()
    if migrated:
        print(f"[memory] 레거시 마이그레이션: {migrated}건")


# ── 로딩 ──────────────────────────────────────────────

def load_all():
    """전체 메모리를 컨텍스트용으로 로드. 1M 컨텍스트를 활용해 필터 없이 전부 주입."""
    conn = _get_conn()
    sections = []

    for mem_type, label in [("about", "프로필"), ("calendar", "일정"),
                             ("notes", "메모"), ("episode", "과거 대화 요약")]:
        rows = conn.execute(
            "SELECT content, created_at FROM memories WHERE type=? ORDER BY created_at",
            (mem_type,),
        ).fetchall()
        if rows:
            lines = [f"- [{r['created_at'][:10]}] {r['content']}" for r in rows]
            sections.append(f"### {label}\n" + "\n".join(lines))

    return "\n\n".join(sections) if sections else ""


def load_history():
    """전체 대화 히스토리 로드."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT user_msg, alf_msg, created_at FROM history ORDER BY id"
    ).fetchall()
    if not rows:
        return ""
    lines = []
    for r in rows:
        lines.append(f"[{r['created_at'][:16]}] User: {r['user_msg']}")
        lines.append(f"[{r['created_at'][:16]}] Alf: {r['alf_msg'][:300]}")
    return "### 대화 기록\n" + "\n".join(lines)


def get_recent_history(limit=5):
    """최근 대화 히스토리 반환 (호환용)."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT user_msg, alf_msg, created_at FROM history "
        "ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    return list(reversed([dict(r) for r in rows]))


# ── 저장 ──────────────────────────────────────────────

def parse_and_save(response):
    """응답에서 [MEM:xxx] 파싱 → DB 저장 → 클린 응답 반환."""
    lines = response.split("\n")
    clean_lines = []
    memories = []

    for line in lines:
        match = MEM_PATTERN.match(line.strip())
        if match:
            mem_type, content = match.group(1), match.group(2).strip()
            if mem_type in VALID_TYPES:
                memories.append((mem_type, content))
        else:
            clean_lines.append(line)

    conn = _get_conn()
    for mem_type, content in memories:
        conn.execute(
            "INSERT INTO memories (type, content) VALUES (?, ?)",
            (mem_type, content),
        )
    if memories:
        conn.commit()
        saved = ", ".join(f"{t}:{c[:20]}" for t, c in memories)
        print(f"[기억 저장] {saved}")

    return "\n".join(clean_lines).rstrip()


def log_history(user_msg, reply):
    """대화 기록 저장."""
    conn = _get_conn()
    conn.execute(
        "INSERT INTO history (user_msg, alf_msg) VALUES (?, ?)",
        (user_msg, reply),
    )
    conn.commit()


def recall(query, limit=5):
    """호환용 — 전체 로드 방식에서는 사용하지 않음."""
    return ""


# ── Compaction ──────────────────────────────────────────

def needs_compaction():
    """compact이 필요한지 확인."""
    conn = _get_conn()
    count = conn.execute("SELECT COUNT(*) FROM history").fetchone()[0]
    return count > COMPACT_THRESHOLD


def compact_history():
    """오래된 히스토리를 날짜별 요약으로 압축.

    최근 COMPACT_KEEP_RECENT건은 원문 유지.
    나머지는 Claude로 요약 → episode 타입 메모리로 저장 → 원본 삭제.
    """
    conn = _get_conn()
    count = conn.execute("SELECT COUNT(*) FROM history").fetchone()[0]
    if count <= COMPACT_THRESHOLD:
        print(f"[compact] 불필요 ({count}/{COMPACT_THRESHOLD}건)")
        return 0

    # 최근 N건의 최소 id 구하기
    keep_row = conn.execute(
        "SELECT id FROM history ORDER BY id DESC LIMIT 1 OFFSET ?",
        (COMPACT_KEEP_RECENT - 1,),
    ).fetchone()
    if not keep_row:
        return 0
    keep_after_id = keep_row["id"]

    # 압축 대상
    old_entries = conn.execute(
        "SELECT id, user_msg, alf_msg, created_at FROM history "
        "WHERE id < ? ORDER BY id",
        (keep_after_id,),
    ).fetchall()

    if not old_entries:
        return 0

    # 날짜별 그룹핑
    by_date = defaultdict(list)
    for entry in old_entries:
        date = entry["created_at"][:10]
        by_date[date].append(entry)

    compacted = 0
    for date, entries in sorted(by_date.items()):
        summary = _summarize_conversations(date, entries)
        if summary:
            conn.execute(
                "INSERT INTO memories (type, content, created_at) VALUES (?, ?, ?)",
                ("episode", summary, date),
            )
            compacted += len(entries)

    # 원본 삭제
    conn.execute("DELETE FROM history WHERE id < ?", (keep_after_id,))
    conn.commit()
    print(f"[compact] {compacted}건 → {len(by_date)}개 요약으로 압축")
    return compacted


def _summarize_conversations(date, entries):
    """하루치 대화를 Claude로 요약."""
    conversation = "\n".join(
        f"User: {e['user_msg']}\nAlf: {e['alf_msg'][:500]}"
        for e in entries
    )

    prompt = (
        f"다음은 {date}의 대화 기록이다. "
        "핵심 내용만 3-5줄로 요약해라. "
        "사용자가 언급한 사실, 선호, 결정 사항 위주로. "
        "불필요한 인사나 형식적 대화는 생략.\n\n"
        f"{conversation}"
    )

    try:
        env = os.environ.copy()
        env.pop("CLAUDECODE", None)
        result = subprocess.run(
            [CLAUDE_CLI, "-p", "--model", "haiku", prompt],
            capture_output=True, text=True, timeout=30, env=env,
        )
        if result.returncode == 0:
            return f"[{date} 대화 요약] {result.stdout.strip()}"
    except Exception as e:
        print(f"[compact] 요약 실패 ({date}): {e}")

    # fallback: LLM 없이 토픽만 추출
    topics = [e["user_msg"][:60] for e in entries]
    return f"[{date} 대화] 주제: {'; '.join(topics)}"

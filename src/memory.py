"""메모리 관리 — SQLite 기반 기억 저장/로딩/검색 + QMD 시맨틱 검색."""

import json
import os
import re
import shutil
import sqlite3
import subprocess
from datetime import datetime, timedelta

MEMORY_DIR = os.path.join(os.path.dirname(__file__), "..", "memory")
DB_PATH = os.path.join(MEMORY_DIR, "alf.db")
QMD_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "qmd")
QMD_BIN = shutil.which("qmd")
QMD_COLLECTION = "alf"

# [MEM:about] 내용, [MEM:calendar] 내용, [MEM:notes] 내용
MEM_PATTERN = re.compile(r"\[MEM:(\w+)\]\s*(.+)")

VALID_TYPES = {"about", "calendar", "notes"}

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


def _migrate_legacy(conn):
    """기존 .md 파일 → SQLite 1회 마이그레이션."""
    count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
    if count > 0:
        return  # 이미 데이터 있으면 스킵

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
                # "- 내용 (2026-03-01)" 형식 파싱
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

    # history.jsonl 마이그레이션
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
    """프롬프트용 메모리 컨텍스트 생성 (선택적 로딩)."""
    conn = _get_conn()
    sections = []

    # about: 전부 (유저 프로필은 항상 필요)
    rows = conn.execute(
        "SELECT content, created_at FROM memories WHERE type='about' ORDER BY created_at"
    ).fetchall()
    if rows:
        lines = [f"- {r['content']}" for r in rows]
        sections.append("### 프로필\n" + "\n".join(lines))

    # calendar: 오늘 기준 ±7일
    now = datetime.now()
    cal_start = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    cal_end = (now + timedelta(days=7)).strftime("%Y-%m-%d")
    rows = conn.execute(
        "SELECT content, created_at FROM memories WHERE type='calendar' "
        "AND content LIKE '%20%-%' ORDER BY content",  # 날짜 포함 항목
    ).fetchall()
    if rows:
        lines = [f"- {r['content']}" for r in rows]
        sections.append("### 일정\n" + "\n".join(lines))

    # notes: 최근 30일
    notes_since = (now - timedelta(days=30)).strftime("%Y-%m-%d")
    rows = conn.execute(
        "SELECT content, created_at FROM memories WHERE type='notes' "
        "AND created_at >= ? ORDER BY created_at DESC LIMIT 20",
        (notes_since,),
    ).fetchall()
    if rows:
        lines = [f"- {r['content']}" for r in rows]
        sections.append("### 메모\n" + "\n".join(lines))

    return "\n\n".join(sections) if sections else ""


def search(query, limit=10):
    """키워드 기반 메모리 검색."""
    conn = _get_conn()
    keywords = query.split()
    if not keywords:
        return []
    where = " AND ".join(["content LIKE ?"] * len(keywords))
    params = [f"%{kw}%" for kw in keywords]
    rows = conn.execute(
        f"SELECT type, content, created_at FROM memories "
        f"WHERE {where} ORDER BY created_at DESC LIMIT ?",
        params + [limit],
    ).fetchall()
    return [dict(r) for r in rows]


def get_recent_history(limit=5):
    """최근 대화 히스토리 반환."""
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
        # QMD 동기화
        for mem_type, content in memories:
            row_id = conn.execute("SELECT MAX(id) FROM memories").fetchone()[0]
            _sync_memory_to_qmd(mem_type, content, row_id)

    return "\n".join(clean_lines).rstrip()


def log_history(user_msg, reply):
    """대화 기록 저장 + QMD용 마크다운 동기화."""
    conn = _get_conn()
    conn.execute(
        "INSERT INTO history (user_msg, alf_msg) VALUES (?, ?)",
        (user_msg, reply),
    )
    conn.commit()
    # QMD 인덱스용 마크다운 파일 생성
    row = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    _sync_history_to_qmd(row, user_msg, reply)


# ── QMD 연동 ──────────────────────────────────────────

def _sync_history_to_qmd(row_id, user_msg, alf_msg):
    """대화 1건을 QMD용 마크다운 파일로 저장."""
    if not QMD_BIN:
        return
    os.makedirs(QMD_DIR, exist_ok=True)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    fname = f"conv-{row_id:04d}.md"
    path = os.path.join(QMD_DIR, fname)
    with open(path, "w") as f:
        f.write(f"# 대화 #{row_id} ({now})\n\n")
        f.write(f"**사용자**: {user_msg}\n\n")
        f.write(f"**알프**: {alf_msg}\n")


def _sync_memory_to_qmd(mem_type, content, mem_id):
    """기억 1건을 QMD용 마크다운 파일로 저장."""
    if not QMD_BIN:
        return
    os.makedirs(QMD_DIR, exist_ok=True)
    now = datetime.now().strftime("%Y-%m-%d")
    fname = f"mem-{mem_type}-{mem_id:04d}.md"
    path = os.path.join(QMD_DIR, fname)
    with open(path, "w") as f:
        f.write(f"# 기억:{mem_type} ({now})\n\n{content}\n")


def qmd_init():
    """QMD 컬렉션 초기 설정 + 기존 데이터 동기화."""
    if not QMD_BIN:
        print("[qmd] qmd 미설치, 스킵")
        return

    os.makedirs(QMD_DIR, exist_ok=True)

    # 컬렉션 존재 확인
    result = subprocess.run(
        [QMD_BIN, "collection", "list"], capture_output=True, text=True
    )
    if QMD_COLLECTION in result.stdout:
        # 이미 등록됨 — update만
        subprocess.run([QMD_BIN, "update"], capture_output=True, text=True)
        return

    # 기존 히스토리 + 메모리를 마크다운으로 내보내기
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, user_msg, alf_msg, created_at FROM history ORDER BY id"
    ).fetchall()
    for r in rows:
        _sync_history_to_qmd(r["id"], r["user_msg"], r["alf_msg"])

    rows = conn.execute(
        "SELECT id, type, content FROM memories ORDER BY id"
    ).fetchall()
    for r in rows:
        _sync_memory_to_qmd(r["type"], r["content"], r["id"])

    # 컬렉션 등록
    subprocess.run(
        [QMD_BIN, "collection", "add", QMD_DIR, "--name", QMD_COLLECTION],
        capture_output=True, text=True,
    )
    subprocess.run(
        [QMD_BIN, "context", "add", f"qmd://{QMD_COLLECTION}",
         "Alf AI 비서와 사용자 간의 대화 기록 및 기억"],
        capture_output=True, text=True,
    )
    print(f"[qmd] 컬렉션 '{QMD_COLLECTION}' 생성 완료")


def recall(query, limit=5):
    """QMD BM25 검색으로 관련 과거 대화/기억 회상."""
    if not QMD_BIN:
        return ""
    try:
        result = subprocess.run(
            [QMD_BIN, "search", query, "--json", "-n", str(limit)],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return ""
        hits = json.loads(result.stdout)
        if not hits:
            return ""

        lines = []
        for hit in hits:
            score = hit.get("score", 0)
            if score < 0.3:
                continue
            snippet = hit.get("snippet", "").strip()
            if not snippet:
                continue
            # QMD diff 마커 제거, 깔끔한 텍스트만 추출
            clean = re.sub(r"@@ .+? @@.*?\n", "", snippet)
            clean = clean.strip()
            if clean:
                lines.append(f"- {clean[:200]}")
        return "\n".join(lines) if lines else ""
    except Exception as e:
        print(f"[qmd] recall 실패: {e}")
        return ""

"""프롬프트 조립 + Claude 호출."""

import glob
import json
import os
import subprocess
import re
import time
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

SKILLS_DIR = os.path.join(os.path.dirname(__file__), "..", "skills")
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
SESSIONS_PATH = os.path.join(os.path.dirname(__file__), "..", "run", "sessions.json")
SESSION_IDLE_MIN = 30
SESSION_MAX_TURNS = 50
SESSION_RESET_HOUR = 4
HISTORY_IN_PROMPT = 5  # 시스템 프롬프트에 포함할 최근 대화 수

ALF_MODEL_CHAT = os.environ.get("ALF_MODEL_CHAT", "sonnet")
ALF_MODEL_MEMORY = os.environ.get("ALF_MODEL_MEMORY", "sonnet")

# 기억/일정/메모 관련 키워드 — sonnet 사용 트리거
MEMORY_KEYWORDS = re.compile(
    r"기억|메모|일정|약속|스케줄|좋아|싫어|선호|습관|알림|리마인드|remember|memo|schedule|remind",
    re.IGNORECASE,
)


def _load_sessions():
    try:
        with open(SESSIONS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_sessions(sessions):
    os.makedirs(os.path.dirname(SESSIONS_PATH), exist_ok=True)
    with open(SESSIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(sessions, f, ensure_ascii=False, indent=2)


def _get_valid_session(sender):
    """유효한 세션 반환. 만료됐으면 None."""
    sessions = _load_sessions()
    s = sessions.get(sender)
    if not s:
        return None

    now = datetime.now()
    last = datetime.fromisoformat(s["last_active"])

    # idle 타임아웃
    if (now - last).total_seconds() > SESSION_IDLE_MIN * 60:
        print(f"[session] idle 만료 ({SESSION_IDLE_MIN}분)")
        return None

    # 일간 리셋 (새벽 4시 이후 + 다른 날)
    created = datetime.fromisoformat(s["created_at"])
    if created.date() != now.date() and now.hour >= SESSION_RESET_HOUR:
        print("[session] 일간 리셋")
        return None

    # 턴 초과
    if s.get("turn_count", 0) >= SESSION_MAX_TURNS:
        print(f"[session] 턴 초과 ({SESSION_MAX_TURNS})")
        return None

    return s


def _save_session(sender, session_id, prev_session):
    """세션 저장/업데이트."""
    sessions = _load_sessions()
    now = datetime.now().isoformat()
    turn = (prev_session or {}).get("turn_count", 0) + 1
    sessions[sender] = {
        "session_id": session_id,
        "created_at": (prev_session or {}).get("created_at", now),
        "last_active": now,
        "turn_count": turn,
    }
    _save_sessions(sessions)
    print(f"[session] saved id={session_id[:12]}... turn={turn}")


def clear_session(sender):
    """세션 삭제 (리셋 명령용)."""
    sessions = _load_sessions()
    if sender in sessions:
        del sessions[sender]
        _save_sessions(sessions)
        print(f"[session] cleared for {sender}")


def build_system_prompt(memory_context, history=None, schedules=None, recall_context=None):
    """스킬 + 메모리 + 히스토리 + 스케줄 + QMD recall을 조합하여 시스템 프롬프트 생성."""
    parts = []

    # 1. 베이스 페르소나
    base_path = os.path.join(SKILLS_DIR, "_base.md")
    if os.path.exists(base_path):
        parts.append(open(base_path).read().strip())

    # 2. trigger=always 스킬 로딩
    for skill_content in _load_skills():
        parts.append(skill_content)

    # 3. 데이터 피드
    feeds = _load_feeds()
    if feeds:
        parts.append(feeds)

    # 4. 메모리 컨텍스트
    if memory_context:
        parts.append(f"## 현재 기억\n\n{memory_context}")

    # 4.5. QMD 관련 기억 (시맨틱 검색 결과)
    if recall_context:
        parts.append(f"## 관련 과거 대화\n\n{recall_context}")

    # 5. 예정된 스케줄
    if schedules:
        lines = ["## 활성 스케줄"]
        for job in schedules:
            lines.append(
                f"- #{job['id']} [{job['type']}] {job['expression']} → {job['message']} "
                f"(다음: {job['next_run'][:16]})"
            )
        parts.append("\n".join(lines))

    # 6. 최근 대화 히스토리
    if history:
        lines = ["## 최근 대화"]
        for h in history:
            lines.append(f"사용자: {h['user_msg']}")
            # 응답이 길면 잘라서 토큰 절약
            alf_msg = h["alf_msg"]
            if len(alf_msg) > 200:
                alf_msg = alf_msg[:200] + "..."
            lines.append(f"Alf: {alf_msg}")
        parts.append("\n".join(lines))

    return "\n\n---\n\n".join(parts)


def _load_skills():
    """skills/*/SKILL.md 중 trigger=always인 것들의 전문 로딩."""
    skills = []
    if not os.path.isdir(SKILLS_DIR):
        return skills

    for name in sorted(os.listdir(SKILLS_DIR)):
        skill_path = os.path.join(SKILLS_DIR, name, "SKILL.md")
        if not os.path.isfile(skill_path):
            continue
        content = open(skill_path).read()

        # YAML frontmatter에서 trigger 확인
        if content.startswith("---"):
            end = content.find("---", 3)
            if end != -1:
                frontmatter = content[3:end]
                if "trigger: on-demand" in frontmatter:
                    continue
                # trigger: always 또는 미지정 → 로딩
                body = content[end + 3:].strip()
                skills.append(body)
            else:
                skills.append(content)
        else:
            skills.append(content)

    return skills


def _load_feeds():
    """data/*.json 자동 로딩 → 프롬프트 섹션 생성."""
    if not os.path.isdir(DATA_DIR):
        return ""

    sections = []
    for path in sorted(glob.glob(os.path.join(DATA_DIR, "*.json"))):
        try:
            with open(path, encoding="utf-8") as f:
                feed = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        source = feed.get("source", os.path.basename(path))
        updated = feed.get("updated_at", "")
        items = feed.get("items", [])

        if items:
            # items 기반 피드 (이메일 등)
            lines = [f"### {source} (갱신: {updated})"]
            for item in items:
                subj = item.get("subject", item.get("title", ""))
                preview = item.get("preview", "")
                sender = item.get("from", "")
                date = item.get("date", "")
                lines.append(f"- [{date}] {sender}: {subj}")
                if preview:
                    lines.append(f"  > {preview[:100]}")
            sections.append("\n".join(lines))
        else:
            # 범용 JSON (stock.json 등) — 10KB 이하만 통째로 주입
            raw = json.dumps(feed, ensure_ascii=False, indent=2)
            if len(raw) > 10_000:
                continue
            header = f"### {source} (갱신: {updated})" if updated else f"### {source}"
            sections.append(header + "\n```json\n" + raw + "\n```")

    if not sections:
        return ""
    return "## 데이터 피드\n\n" + "\n\n".join(sections)


def select_model(message):
    """메시지 내용에 따라 모델 선택."""
    if MEMORY_KEYWORDS.search(message):
        return ALF_MODEL_MEMORY
    return ALF_MODEL_CHAT


def _run_claude(cmd, env):
    """Claude subprocess 실행 + JSON 파싱."""
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, env=env)
    if result.returncode != 0:
        print(f"[claude 에러] {result.stderr.strip()}")
        return None
    return json.loads(result.stdout)


def ask(message, memory_context, sender=None, history=None, schedules=None, recall_context=None):
    """시스템 프롬프트 조립 → Claude 호출 → 응답 반환."""
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)

    t0 = time.perf_counter()
    session = _get_valid_session(sender) if sender else None
    print(f"    ⏱ session_lookup: {time.perf_counter() - t0:.3f}s")

    if session:
        # resume 모드: 기존 세션 이어가기
        cmd = [
            "/Users/afred/.local/bin/claude", "-p",
            "--resume", session["session_id"],
            "--output-format", "json",
            message,
        ]
        print(f"[brain] resume={session['session_id'][:12]}... turn={session['turn_count']}")

        t0 = time.perf_counter()
        data = _run_claude(cmd, env)
        print(f"    ⏱ claude_resume: {time.perf_counter() - t0:.3f}s")

        # resume 실패 → 새 세션으로 fallback
        if data is None:
            print("[brain] resume 실패, 새 세션으로 fallback")
            if sender:
                clear_session(sender)
            session = None

    if not session:
        # 새 세션 모드
        t0 = time.perf_counter()
        system_prompt = build_system_prompt(memory_context, history=history, schedules=schedules, recall_context=recall_context)
        print(f"    ⏱ build_prompt: {time.perf_counter() - t0:.3f}s ({len(system_prompt)}자)")

        model = select_model(message)
        cmd = [
            "/Users/afred/.local/bin/claude", "-p",
            "--model", model,
            "--output-format", "json",
            "--allowedTools", "mcp__fetch", "WebFetch", "Read",
            "--system-prompt", system_prompt,
            message,
        ]
        print(f"[brain] new session, model={model}")

        t0 = time.perf_counter()
        data = _run_claude(cmd, env)
        print(f"    ⏱ claude_run: {time.perf_counter() - t0:.3f}s")

    if data is None:
        return None

    # 세션 저장
    t0 = time.perf_counter()
    if sender and "session_id" in data:
        _save_session(sender, data["session_id"], session)
    print(f"    ⏱ session_save: {time.perf_counter() - t0:.3f}s")

    return data["result"]

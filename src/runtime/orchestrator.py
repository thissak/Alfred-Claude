"""이벤트 기반 메시지 오케스트레이터.

inbox 메시지를 받아 Claude 응답을 생성하고 outbox에 적재한다.
"""

import glob
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

try:
    import memory as legacy_memory
    import scheduler as legacy_scheduler
    from runtime.context import build_message_context
    from runtime.event_bus import build_message_received
    from tools.memory import clean_and_store, log_history
    from tools.notes import clean_and_store as clean_and_store_note
    from tools.schedule import clean_and_store as clean_and_store_schedule
except ModuleNotFoundError:
    from src import memory as legacy_memory
    from src import scheduler as legacy_scheduler
    from src.runtime.context import build_message_context
    from src.runtime.event_bus import build_message_received
    from src.tools.memory import clean_and_store, log_history
    from src.tools.notes import clean_and_store as clean_and_store_note
    from src.tools.schedule import clean_and_store as clean_and_store_schedule

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
OUTBOX = PROJECT_ROOT / "run" / "outbox"
SKILLS_DIR = str(PROJECT_ROOT / "skills")
DATA_DIR = str(PROJECT_ROOT / "data")
CLAUDE_CLI = "/Users/afred/.local/bin/claude"

MODEL = os.environ.get("ALF_MODEL_CHAT", "sonnet")
MEMORY_PROTOCOL = """When the user shares a durable preference, profile fact, plan, or note worth remembering, append memory commands on separate trailing lines:
[MEM:about] stable preference or profile fact
[MEM:calendar] dated plan or appointment
[MEM:notes] lightweight note or todo
Only emit memory lines when something is worth saving, and keep the normal user-facing reply above them."""
SCHEDULE_PROTOCOL = """When the user asks for reminders or recurring notifications, append schedule commands on separate trailing lines:
[SCHED:at YYYY-MM-DD HH:MM] message
[SCHED:daily HH:MM] message
[SCHED:every SECONDS] message
[SCHED:cancel JOB_ID]
Keep the normal user-facing reply above them."""
NOTE_PROTOCOL = """When the user asks for a structured note to save, append a note block at the end:
[NOTE:Title]
markdown body
[/NOTE]
Keep the normal user-facing reply above the note block."""

_runtime_initialized = False


def ensure_runtime_ready():
    """메모리/스케줄 저장 계층 초기화."""
    global _runtime_initialized
    if _runtime_initialized:
        return
    legacy_memory.init()
    legacy_scheduler.init(legacy_memory.DB_PATH)
    _runtime_initialized = True


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
        if content.startswith("---"):
            end = content.find("---", 3)
            if end != -1:
                frontmatter = content[3:end]
                if "trigger: on-demand" in frontmatter:
                    continue
                skills.append(content[end + 3:].strip())
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
            raw = json.dumps(feed, ensure_ascii=False, indent=2)
            if len(raw) > 10_000:
                continue
            header = f"### {source} (갱신: {updated})" if updated else f"### {source}"
            sections.append(header + "\n```json\n" + raw + "\n```")
    if not sections:
        return ""
    return "## 데이터 피드\n\n" + "\n\n".join(sections)


def build_system_prompt(message):
    """페르소나 + 스킬 + 피드 + 프로토콜 + 메모리 컨텍스트를 조합."""
    parts = []

    # 0. 현재 날짜/시간
    now = datetime.now()
    weekdays = ["월", "화", "수", "목", "금", "토", "일"]
    parts.append(f"현재: {now.strftime('%Y-%m-%d')}({weekdays[now.weekday()]}) {now.strftime('%H:%M')}")

    # 1. 베이스 페르소나
    base_path = os.path.join(SKILLS_DIR, "_base.md")
    if os.path.exists(base_path):
        parts.append(open(base_path).read().strip())

    # 2. 스킬
    for skill_content in _load_skills():
        parts.append(skill_content)

    # 3. 데이터 피드
    feeds = _load_feeds()
    if feeds:
        parts.append(feeds)

    # 4. 프로토콜
    parts.extend([MEMORY_PROTOCOL, SCHEDULE_PROTOCOL, NOTE_PROTOCOL])

    # 5. 메모리 컨텍스트
    context = build_message_context(message)
    if context:
        parts.append(context)

    return "\n\n---\n\n".join(parts)


def ask_claude(message, system=""):
    """Claude CLI 호출."""
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)

    cmd = [
        CLAUDE_CLI, "-p",
        "--model", MODEL,
        "--output-format", "json",
        "--allowedTools", "mcp__fetch", "WebFetch", "WebSearch", "Read",
        "--system-prompt", system,
        message,
    ]
    print(f"[brain] claude -p model={MODEL}")

    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=120, env=env,
    )
    if result.returncode != 0:
        print(f"[claude 에러] {result.stderr.strip()}")
        return ""

    data = json.loads(result.stdout)
    return data.get("result", "")


def write_response(recipient, message):
    """응답을 outbox JSON으로 적재."""
    OUTBOX.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    payload = {
        "recipient": recipient,
        "message": message,
        "timestamp": datetime.now().isoformat(),
    }
    path = OUTBOX / f"{ts}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"  [outbox] {path.name}")
    return path


def mark_done(event):
    """처리 완료된 inbox 파일 삭제."""
    source_path = event.get("source_path")
    if not source_path:
        return
    Path(source_path).unlink(missing_ok=True)


def handle_event(event):
    """정규화된 이벤트를 처리하고 필요 시 응답을 발행."""
    if event["type"] != "message.received":
        raise ValueError(f"unsupported event type: {event['type']}")

    ensure_runtime_ready()

    sender = event["sender"]
    text = event["text"]
    print(f"[event] {event['type']} from={sender}")
    print(f"[수신] {sender}: {text}")

    # 중복 처리 방지: 처리 시작 시 즉시 inbox 파일 제거
    mark_done(event)

    # 주식 관련 키워드 감지 → data/stock.json 실시간 갱신
    _STOCK_KEYWORDS = ["미장", "주식", "시황", "종목", "주가", "포트폴리오", "내 주식", "급등", "거래량"]
    if any(kw in text for kw in _STOCK_KEYWORDS):
        print("[stock] 주식 키워드 감지 → fetch_stock.py 실행")
        subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "skills" / "stock" / "fetch_stock.py")],
            cwd=str(PROJECT_ROOT),
            timeout=30,
        )

    system_prompt = build_system_prompt(text)
    raw_reply = ask_claude(text, system=system_prompt)
    reply, note_saved = clean_and_store_note(raw_reply)
    reply, schedule_actions = clean_and_store_schedule(reply)
    reply, saved_memories = clean_and_store(reply)
    print(f"[응답] {reply}")
    if note_saved:
        print("[note] saved")
    if schedule_actions:
        print(f"[schedule] {len(schedule_actions)} action(s)")
    if saved_memories:
        print(f"[memory] {len(saved_memories)} saved")

    log_history(text, reply)
    write_response(sender, reply)

    # compact 체크 (응답 발송 후)
    if legacy_memory.needs_compaction():
        print("[compact] 임계값 초과, 히스토리 압축 시작")
        legacy_memory.compact_history()

    return reply


def handle_scheduled_job(job, recipient):
    """만기된 스케줄 잡을 처리해 outbox에 응답을 적재."""
    ensure_runtime_ready()

    prompt = f"[스케줄 알림] {job['message']}"
    print(f"[event] schedule.due id={job['id']} recipient={recipient}")
    print(f"[수신] {prompt}")

    system_prompt = build_system_prompt(prompt)
    raw_reply = ask_claude(prompt, system=system_prompt)
    reply, note_saved = clean_and_store_note(raw_reply)
    reply, schedule_actions = clean_and_store_schedule(reply)
    reply, saved_memories = clean_and_store(reply)
    print(f"[응답] {reply}")
    if note_saved:
        print("[note] saved")
    if schedule_actions:
        print(f"[schedule] {len(schedule_actions)} action(s)")
    if saved_memories:
        print(f"[memory] {len(saved_memories)} saved")

    log_history(prompt, reply)
    write_response(recipient, reply)
    return reply


def handle_inbox_message(msg):
    """기존 inbox JSON 인터페이스와의 호환용 진입점."""
    event = build_message_received(msg)
    return handle_event(event)

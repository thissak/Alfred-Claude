"""이벤트 기반 메시지 오케스트레이터.

첫 단계에서는 inbox 메시지를 받아 GPT 응답을 생성하고 outbox에 적재한다.
추후 memory/tool/notifier 결합 지점으로 확장한다.
"""

import json
from datetime import datetime
from pathlib import Path

import httpx

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
AUTH_PATH = Path.home() / ".codex" / "auth.json"

MODEL = "gpt-5.4"
SYSTEM_PROMPT = "You are a friendly Korean-speaking personal assistant. 간결하게 답해."
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


def build_system_prompt(message):
    """기본 지시문과 메시지별 메모리 컨텍스트를 합친다."""
    context = build_message_context(message)
    parts = [SYSTEM_PROMPT, MEMORY_PROTOCOL, SCHEDULE_PROTOCOL, NOTE_PROTOCOL]
    if not context:
        return "\n\n".join(parts)
    parts.append(context)
    return "\n\n".join(parts)


def _get_token():
    with open(AUTH_PATH) as f:
        return json.load(f)["tokens"]["access_token"]


def ask_gpt(message, system=SYSTEM_PROMPT):
    """Codex OAuth 경유 GPT 호출."""
    token = _get_token()
    full = ""
    with httpx.stream(
        "POST",
        "https://chatgpt.com/backend-api/codex/responses",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL,
            "instructions": system,
            "input": [{"role": "user", "content": message}],
            "store": False,
            "stream": True,
        },
        timeout=60,
    ) as response:
        if response.status_code != 200:
            raise RuntimeError(
                f"GPT error {response.status_code}: {response.read().decode()[:200]}"
            )
        for line in response.iter_lines():
            if not line.startswith("data: "):
                continue
            chunk = line[6:]
            if chunk == "[DONE]":
                break
            try:
                data = json.loads(chunk)
            except json.JSONDecodeError:
                continue
            if data.get("type") == "response.output_text.delta":
                full += data.get("delta", "")
    return full


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

    system_prompt = build_system_prompt(text)
    raw_reply = ask_gpt(text, system=system_prompt)
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
    mark_done(event)
    return reply


def handle_scheduled_job(job, recipient):
    """만기된 스케줄 잡을 처리해 outbox에 응답을 적재."""
    ensure_runtime_ready()

    prompt = f"[스케줄 알림] {job['message']}"
    print(f"[event] schedule.due id={job['id']} recipient={recipient}")
    print(f"[수신] {prompt}")

    system_prompt = build_system_prompt(prompt)
    raw_reply = ask_gpt(prompt, system=system_prompt)
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

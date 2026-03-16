#!/usr/bin/env python3
"""Alf — iMessage AI 비서. chat.db 폴링 → Brain → Memory → 답장 + 스케줄러."""

import os
import re
import sqlite3
import subprocess
import sys
import time
import traceback
from contextlib import contextmanager

from dotenv import load_dotenv

import brain
import memory
import scheduler

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "research"))
import save_note

load_dotenv()

DB_PATH = os.path.expanduser("~/Library/Messages/chat.db")
MY_NUMBER = os.environ["ALF_MY_NUMBER"]
POLL_INTERVAL = 2
DEDUP_WINDOW = 10  # 동일 메시지 무시 윈도우 (초)
RESET_RE = re.compile(r"^(새\s*대화|리셋|reset|new\s*chat)$", re.IGNORECASE)


@contextmanager
def timed(label):
    """단계별 소요시간 측정."""
    t0 = time.perf_counter()
    yield
    elapsed = time.perf_counter() - t0
    print(f"  ⏱ {label}: {elapsed:.3f}s")


def get_max_rowid():
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    rowid = conn.execute("SELECT MAX(ROWID) FROM message").fetchone()[0] or 0
    conn.close()
    return rowid


def poll(last_rowid):
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    rows = conn.execute(
        """
        SELECT m.ROWID, m.text, m.attributedBody, h.id
        FROM message m
        LEFT JOIN handle h ON m.handle_id = h.ROWID
        WHERE m.ROWID > ? AND m.is_from_me = 0
          AND m.associated_message_type = 0
        ORDER BY m.ROWID ASC
        """,
        (last_rowid,),
    ).fetchall()
    conn.close()
    return rows


def extract_text(text, attributed_body):
    """text 컬럼 우선, NULL이면 attributedBody에서 추출."""
    if text:
        return text.strip()
    if not attributed_body:
        return None
    try:
        blob = bytes(attributed_body)
        marker = b"NSString"
        idx = blob.find(marker)
        if idx == -1:
            return None
        idx += len(marker)
        length_byte = blob[idx]
        if length_byte == 0x01:
            idx += 1
            length = blob[idx]
            idx += 1
        else:
            idx += 1
            length = int.from_bytes(blob[idx : idx + 2], "little")
            idx += 2
        return blob[idx : idx + length].decode("utf-8").strip()
    except Exception:
        return "[미디어 메시지]"


def escape_applescript(text):
    """AppleScript 문자열 이스케이프."""
    return text.replace("\\", "\\\\").replace('"', '\\"')


def send_imessage(recipient, text):
    escaped = escape_applescript(text)
    script = f'''
    tell application "Messages"
        set targetService to 1st service whose service type = iMessage
        set targetBuddy to buddy "{recipient}" of targetService
        send "{escaped}" to targetBuddy
    end tell'''
    for attempt in range(2):
        result = subprocess.run(
            ["osascript", "-e", script], capture_output=True, text=True
        )
        if result.returncode == 0:
            return True
        if attempt == 0:
            time.sleep(1)
    print(f"[발신 실패] {result.stderr.strip()}")
    return False


def process_response(raw_reply):
    """Claude 응답 파싱: 노트 → 스케줄 → 기억 → 클린 응답."""
    # 노트 파싱 → Apple Notes 저장
    raw_reply, note_saved = save_note.parse_and_save(raw_reply)

    # 스케줄 파싱 → DB 저장
    raw_reply = scheduler.parse_and_save(raw_reply)

    # 기억 파싱 → DB 저장, 클린 응답 반환
    reply = memory.parse_and_save(raw_reply)

    if note_saved:
        reply += "\n메모앱에 정리해뒀어, 확인해봐."

    return reply, note_saved


def handle_message(content, sent_texts):
    """단일 메시지 처리 파이프라인."""
    t_total = time.perf_counter()

    # 컨텍스트 조립
    with timed("memory.load_all"):
        memory_context = memory.load_all()

    with timed("context_load"):
        history = memory.get_recent_history(brain.HISTORY_IN_PROMPT)
        schedules = scheduler.get_active_jobs()

    # QMD 관련 기억 검색
    with timed("memory.recall (QMD)"):
        recall_context = memory.recall(content)

    # Claude 호출
    with timed("brain.ask (Claude 호출)"):
        raw_reply = brain.ask(
            content, memory_context, sender=MY_NUMBER,
            history=history, schedules=schedules,
            recall_context=recall_context,
        )

    if raw_reply is None:
        print("[스킵] Claude 응답 실패")
        return

    # 응답 파싱
    with timed("process_response"):
        reply, _ = process_response(raw_reply)

    # 대화 기록
    with timed("memory.log_history"):
        memory.log_history(content, reply)

    # 발신
    with timed("send_imessage"):
        send_imessage(MY_NUMBER, reply)
        sent_texts[reply] = time.time()

    print(f"  ⏱ === 총 소요: {time.perf_counter() - t_total:.3f}s ===")
    print(f"[응답] {reply[:80]}...")


def handle_scheduled_jobs(sent_texts):
    """만기된 스케줄 잡 실행."""
    due_jobs = scheduler.get_due_jobs()
    if not due_jobs:
        return

    for job in due_jobs:
        print(f"[sched] 실행 #{job['id']}: {job['message'][:40]}")
        scheduler.mark_run(job["id"])

        # 스케줄 메시지를 프롬프트로 보내 Claude가 응답 생성
        memory_context = memory.load_all()
        history = memory.get_recent_history(brain.HISTORY_IN_PROMPT)
        schedules = scheduler.get_active_jobs()

        prompt = f"[스케줄 알림] {job['message']}"
        raw_reply = brain.ask(
            prompt, memory_context, sender=MY_NUMBER,
            history=history, schedules=schedules,
        )

        if raw_reply is None:
            print(f"[sched] Claude 응답 실패 #{job['id']}")
            continue

        reply, _ = process_response(raw_reply)
        memory.log_history(prompt, reply)
        send_imessage(MY_NUMBER, reply)
        sent_texts[reply] = time.time()
        print(f"[sched] 발신 #{job['id']}: {reply[:60]}...")


def main():
    memory.init()
    memory.qmd_init()
    scheduler.init(memory.DB_PATH)

    print(f"Alf 시작 — 감시 대상: {MY_NUMBER}")
    last_rowid = get_max_rowid()
    print(f"현재 ROWID: {last_rowid}, 폴링 시작...")
    sent_texts = {}   # {text: timestamp} — 에코 감지용
    recent_msgs = {}  # {text: timestamp} — 수신 중복 감지용

    while True:
        try:
            # 1. iMessage 수신 처리
            messages = poll(last_rowid)
            for rowid, text, body, sender in messages:
                if sender != MY_NUMBER:
                    continue
                content = extract_text(text, body)
                if not content:
                    continue

                now = time.time()

                # 에코 감지: Alf가 보낸 텍스트가 되돌아온 경우
                if content in sent_texts:
                    del sent_texts[content]
                    print(f"[에코 무시] {content[:40]}...")
                    continue

                # 중복 수신 감지: 같은 텍스트가 N초 이내 다시 온 경우
                if content in recent_msgs and (now - recent_msgs[content]) < DEDUP_WINDOW:
                    print(f"[중복 무시] {content[:40]}... ({now - recent_msgs[content]:.1f}s)")
                    continue
                recent_msgs[content] = now

                print(f"[수신] {content}")

                # 리셋 명령 처리
                if RESET_RE.match(content.strip()):
                    brain.clear_session(MY_NUMBER)
                    reply = "새 대화 시작할게!"
                    send_imessage(MY_NUMBER, reply)
                    sent_texts[reply] = time.time()
                    last_rowid = rowid
                    continue

                handle_message(content, sent_texts)
                last_rowid = rowid

            if messages:
                last_rowid = max(last_rowid, messages[-1][0])

            # 2. 스케줄 잡 실행
            handle_scheduled_jobs(sent_texts)

            # 3. 오래된 dedup 엔트리 정리 (60초 이상)
            cutoff = time.time() - 60
            sent_texts = {k: v for k, v in sent_texts.items() if v > cutoff}
            recent_msgs = {k: v for k, v in recent_msgs.items() if v > cutoff}

        except KeyboardInterrupt:
            print("\nAlf 종료.")
            break
        except Exception as e:
            print(f"[에러] {e}")
            traceback.print_exc()
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()

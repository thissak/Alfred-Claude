#!/usr/bin/env python3
"""Alf Bridge — iMessage ↔ 파일 기반 IPC. Claude Code가 처리하는 구조.

chat.db 폴링 → run/inbox/ 에 메시지 저장
run/outbox/ 에 응답 파일 있으면 → iMessage 발신
"""

import json
import os
import re
import sqlite3
import subprocess
import time
import traceback
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from heartbeat import beat

DB_PATH = os.path.expanduser("~/Library/Messages/chat.db")
MY_NUMBER = os.environ["ALF_MY_NUMBER"]
POLL_INTERVAL = 1
DEDUP_WINDOW = 10

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INBOX = PROJECT_ROOT / "run" / "inbox"
OUTBOX = PROJECT_ROOT / "run" / "outbox"


def _ensure_dirs():
    INBOX.mkdir(parents=True, exist_ok=True)
    OUTBOX.mkdir(parents=True, exist_ok=True)


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


def write_inbox(content, sender):
    """메시지를 inbox에 JSON 파일로 저장."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    msg = {
        "sender": sender,
        "message": content,
        "timestamp": datetime.now().isoformat(),
    }
    path = INBOX / f"{ts}.json"
    path.write_text(json.dumps(msg, ensure_ascii=False, indent=2))
    print(f"[inbox] {path.name}: {content[:60]}")


def process_outbox(sent_texts):
    """outbox에 있는 응답 파일을 읽어 iMessage 발신 후 삭제."""
    for path in sorted(OUTBOX.glob("*.json")):
        try:
            msg = json.loads(path.read_text())
            recipient = msg.get("recipient", MY_NUMBER)
            text = msg["message"]
            send_imessage(recipient, text)
            sent_texts[text] = time.time()
            print(f"[outbox] 발신: {text[:60]}...")
            path.unlink()
        except Exception as e:
            print(f"[outbox 에러] {path.name}: {e}")
            # 깨진 파일은 삭제
            path.unlink(missing_ok=True)


def main():
    _ensure_dirs()
    print(f"Alf Bridge 시작 — 감시: {MY_NUMBER}")
    print(f"  inbox:  {INBOX}")
    print(f"  outbox: {OUTBOX}")

    last_rowid = get_max_rowid()
    print(f"현재 ROWID: {last_rowid}, 폴링 시작...")
    beat("bridge", "ok", "시작됨")
    sent_texts = {}
    recent_msgs = {}

    while True:
        try:
            # 1. iMessage 수신 → inbox
            messages = poll(last_rowid)
            for rowid, text, body, sender in messages:
                if sender != MY_NUMBER:
                    continue
                content = extract_text(text, body)
                if not content:
                    continue

                now = time.time()

                # 에코 감지
                if content in sent_texts:
                    del sent_texts[content]
                    continue

                # 중복 감지
                if content in recent_msgs and (now - recent_msgs[content]) < DEDUP_WINDOW:
                    continue
                recent_msgs[content] = now

                print(f"[수신] {content}")
                write_inbox(content, sender)
                last_rowid = rowid

            if messages:
                last_rowid = max(last_rowid, messages[-1][0])

            # 2. outbox → iMessage 발신
            process_outbox(sent_texts)

            # 3. 정리
            cutoff = time.time() - 60
            sent_texts = {k: v for k, v in sent_texts.items() if v > cutoff}
            recent_msgs = {k: v for k, v in recent_msgs.items() if v > cutoff}

            beat("bridge", "ok", "폴링 중")

        except KeyboardInterrupt:
            print("\nAlf Bridge 종료.")
            break
        except Exception as e:
            beat("bridge", "error", str(e)[:100])
            print(f"[에러] {e}")
            traceback.print_exc()
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()

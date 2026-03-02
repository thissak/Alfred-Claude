#!/usr/bin/env python3
"""Alf — iMessage AI 비서. chat.db 폴링 → Brain → Memory → 답장."""

import os
import sqlite3
import subprocess
import sys
import time
import traceback

from dotenv import load_dotenv

import brain
import memory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "research"))
import save_note

load_dotenv()

DB_PATH = os.path.expanduser("~/Library/Messages/chat.db")
MY_NUMBER = os.environ["ALF_MY_NUMBER"]
POLL_INTERVAL = 2


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


def main():
    memory.init()
    print(f"Alf 시작 — 감시 대상: {MY_NUMBER}")
    last_rowid = get_max_rowid()
    print(f"현재 ROWID: {last_rowid}, 폴링 시작...")
    sent_texts = set()

    while True:
        try:
            messages = poll(last_rowid)
            for rowid, text, body, sender in messages:
                if sender != MY_NUMBER:
                    continue
                content = extract_text(text, body)
                if not content:
                    continue
                if content in sent_texts:
                    sent_texts.discard(content)
                    print(f"[에코 무시] {content[:40]}...")
                    continue

                print(f"[수신] {content}")

                # 메모리 로딩 → Claude 호출
                memory_context = memory.load_all()
                raw_reply = brain.ask(content, memory_context)

                if raw_reply is None:
                    print("[스킵] Claude 응답 실패")
                    last_rowid = rowid
                    continue

                # 노트 파싱 → Apple Notes 저장
                raw_reply, note_saved = save_note.parse_and_save(raw_reply)

                # 기억 파싱 + 저장, 클린 응답 추출
                reply = memory.parse_and_save(raw_reply)

                # 노트 저장됐으면 안내 추가
                if note_saved:
                    reply += "\n메모앱에 정리해뒀어, 확인해봐."

                # 대화 기록
                memory.log_history(content, reply)

                print(f"[응답] {reply[:80]}...")
                send_imessage(MY_NUMBER, reply)
                sent_texts.add(reply)
                last_rowid = rowid

            if messages:
                last_rowid = max(last_rowid, messages[-1][0])
        except KeyboardInterrupt:
            print("\nAlf 종료.")
            break
        except Exception as e:
            print(f"[에러] {e}")
            traceback.print_exc()
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()

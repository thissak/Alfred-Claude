#!/usr/bin/env python3
"""Inbox 프로세서 — inbox 메시지를 읽어 오케스트레이터에 전달.

Usage:
  python3 src/process_inbox.py          # 한 번 처리
  python3 src/process_inbox.py --watch  # 계속 감시 (2초 폴링)
"""

import argparse
import fcntl
import sys
import time
import traceback
from pathlib import Path

import json

try:
    from runtime.orchestrator import MODEL, handle_inbox_message
except ModuleNotFoundError:
    from src.runtime.orchestrator import MODEL, handle_inbox_message

from heartbeat import beat

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INBOX = PROJECT_ROOT / "run" / "inbox"
FAILED = INBOX / "failed"
LOCK_FILE = PROJECT_ROOT / "run" / "inbox.lock"


def quarantine(msg, error):
    """처리 실패한 inbox 파일을 failed/ 로 이동 — 무한 재처리 방지."""
    src_path = msg.get("_path")
    if not src_path:
        return
    src = Path(src_path)
    if not src.exists():
        return
    FAILED.mkdir(parents=True, exist_ok=True)
    dest = FAILED / src.name
    try:
        src.rename(dest)
        print(f"[격리] {src.name} → failed/ ({error})")
    except OSError as e:
        print(f"[격리 실패] {src.name}: {e}")


def acquire_lock():
    """단일 인스턴스 보장. 이미 실행 중이면 즉시 종료."""
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    lock_fd = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("[inbox] 이미 다른 인스턴스가 실행 중 — 종료합니다.")
        sys.exit(0)
    return lock_fd


def get_pending():
    if not INBOX.exists():
        return []
    msgs = []
    for f in sorted(INBOX.glob("*.json")):
        try:
            data = json.loads(f.read_text())
            data["_path"] = str(f)
            msgs.append(data)
        except (json.JSONDecodeError, OSError):
            continue
    return msgs


def process(msg):
    handle_inbox_message(msg)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--watch", action="store_true", help="계속 감시 모드")
    args = parser.parse_args()

    _lock = acquire_lock()  # noqa: F841 — held until process exits

    if args.watch:
        print(f"Inbox 감시 시작: {INBOX}")
        print(f"모델: {MODEL}")
        beat("inbox", "ok", "감시 시작")
        while True:
            pending = get_pending()
            for m in pending:
                try:
                    beat("inbox", "ok", f"처리 중: {m.get('message', '')[:30]}")
                    process(m)
                except Exception as e:
                    beat("inbox", "error", str(e)[:100])
                    print(f"[에러] {e}")
                    traceback.print_exc()
                    quarantine(m, str(e)[:100])
            beat("inbox", "idle" if not pending else "ok", f"대기 중 ({len(pending)}건 처리)")
            time.sleep(2)
    else:
        msgs = get_pending()
        if not msgs:
            print("처리할 메시지 없음")
            return
        for m in msgs:
            try:
                process(m)
            except Exception as e:
                print(f"[에러] {e}")
                traceback.print_exc()
                quarantine(m, str(e)[:100])


if __name__ == "__main__":
    main()

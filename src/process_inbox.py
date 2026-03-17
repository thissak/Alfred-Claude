#!/usr/bin/env python3
"""Inbox 프로세서 — inbox 메시지를 GPT로 처리하고 outbox에 응답 작성.

Usage:
  python3 src/process_inbox.py          # 한 번 처리
  python3 src/process_inbox.py --watch  # 계속 감시 (2초 폴링)
"""

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INBOX = PROJECT_ROOT / "run" / "inbox"
OUTBOX = PROJECT_ROOT / "run" / "outbox"
AUTH_PATH = Path.home() / ".codex" / "auth.json"

MODEL = "gpt-5.4"
SYSTEM_PROMPT = "You are a friendly Korean-speaking personal assistant. 간결하게 답해."


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
    ) as r:
        if r.status_code != 200:
            raise RuntimeError(f"GPT error {r.status_code}: {r.read().decode()[:200]}")
        for line in r.iter_lines():
            if line.startswith("data: "):
                chunk = line[6:]
                if chunk == "[DONE]":
                    break
                try:
                    d = json.loads(chunk)
                    if d.get("type") == "response.output_text.delta":
                        full += d.get("delta", "")
                except json.JSONDecodeError:
                    pass
    return full


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


def write_response(recipient, message):
    OUTBOX.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    resp = {
        "recipient": recipient,
        "message": message,
        "timestamp": datetime.now().isoformat(),
    }
    path = OUTBOX / f"{ts}.json"
    path.write_text(json.dumps(resp, ensure_ascii=False, indent=2))
    print(f"  [outbox] {path.name}")
    return path


def mark_done(msg):
    Path(msg["_path"]).unlink(missing_ok=True)


def process(msg):
    sender = msg["sender"]
    text = msg["message"]
    print(f"[수신] {sender}: {text}")

    reply = ask_gpt(text)
    print(f"[응답] {reply}")

    write_response(sender, reply)
    mark_done(msg)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--watch", action="store_true", help="계속 감시 모드")
    args = parser.parse_args()

    if args.watch:
        print(f"Inbox 감시 시작: {INBOX}")
        print(f"모델: {MODEL}")
        while True:
            for m in get_pending():
                try:
                    process(m)
                except Exception as e:
                    print(f"[에러] {e}")
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


if __name__ == "__main__":
    main()

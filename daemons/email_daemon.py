"""네이버 이메일 IMAP IDLE 데몬 — 최근 메일 수집 → data/email.json."""

import json
import os
import sys
import time
from datetime import datetime

from dotenv import load_dotenv
from imap_tools import MailBox, AND

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

EMAIL = os.environ.get("NAVER_EMAIL", "")
PASSWORD = os.environ.get("NAVER_APP_PASSWORD", "")
IMAP_HOST = "imap.naver.com"
FETCH_COUNT = 10
IDLE_TIMEOUT = 29 * 60  # 29분 (IMAP 권장 최대)
RETRY_DELAY = 30

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
JSON_PATH = os.path.join(DATA_DIR, "email.json")


def fetch_and_save(mailbox):
    """최근 N건 fetch → JSON 저장."""
    msgs = list(mailbox.fetch(AND(all=True), limit=FETCH_COUNT, reverse=True))
    items = []
    for m in msgs:
        preview = (m.text or m.html or "")[:200].replace("\n", " ").strip()
        items.append({
            "uid": str(m.uid),
            "date": m.date.strftime("%Y-%m-%d %H:%M") if m.date else "",
            "from": str(m.from_),
            "subject": m.subject or "",
            "preview": preview,
        })

    data = {
        "source": "naver_email",
        "updated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "items": items,
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[email_daemon] {len(items)}건 저장 → {JSON_PATH}")


def run():
    """IMAP 접속 → fetch → IDLE 루프."""
    if not EMAIL or not PASSWORD:
        print("[email_daemon] NAVER_EMAIL / NAVER_APP_PASSWORD 미설정")
        sys.exit(1)

    while True:
        try:
            with MailBox(IMAP_HOST).login(EMAIL, PASSWORD) as mb:
                print(f"[email_daemon] {EMAIL} 로그인 성공")
                fetch_and_save(mb)

                while True:
                    # IDLE 대기 — 새 메일 도착 시 리턴
                    responses = mb.idle.wait(timeout=IDLE_TIMEOUT)
                    if responses:
                        print(f"[email_daemon] IDLE 이벤트: {len(responses)}건")
                    else:
                        print("[email_daemon] IDLE 타임아웃, 재연결")
                    fetch_and_save(mb)

        except KeyboardInterrupt:
            print("[email_daemon] 종료")
            break
        except Exception as e:
            print(f"[email_daemon] 에러: {e}, {RETRY_DELAY}초 후 재시도")
            time.sleep(RETRY_DELAY)


if __name__ == "__main__":
    run()

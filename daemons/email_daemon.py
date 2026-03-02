"""네이버 이메일 IMAP 폴링 데몬 — 최근 메일 수집 → data/email.json."""

import json
import os
import re
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
POLL_INTERVAL = 5 * 60  # 5분마다 폴링
RETRY_DELAY = 30

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
EMAILS_DIR = os.path.join(DATA_DIR, "emails")
JSON_PATH = os.path.join(DATA_DIR, "email.json")


def _strip_html(html):
    """HTML 태그 제거 → 텍스트만 추출."""
    text = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def fetch_and_save(mailbox):
    """최근 N건 fetch → JSON 저장 + 전체 본문 파일 저장."""
    msgs = list(mailbox.fetch(AND(all=True), limit=FETCH_COUNT, reverse=True))
    os.makedirs(EMAILS_DIR, exist_ok=True)
    items = []
    for m in msgs:
        body_text = m.text or (_strip_html(m.html) if m.html else "")
        preview = body_text[:200].replace("\n", " ").strip()

        # 전체 본문 파일 저장
        with open(os.path.join(EMAILS_DIR, f"{m.uid}.txt"), "w", encoding="utf-8") as bf:
            bf.write(f"From: {m.from_}\nSubject: {m.subject}\nDate: {m.date}\n\n")
            bf.write(body_text or "(본문 없음)")

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
    """IMAP 접속 → fetch → 폴링 루프."""
    if not EMAIL or not PASSWORD:
        print("[email_daemon] NAVER_EMAIL / NAVER_APP_PASSWORD 미설정")
        sys.exit(1)

    while True:
        try:
            with MailBox(IMAP_HOST).login(EMAIL, PASSWORD) as mb:
                print(f"[email_daemon] {EMAIL} 로그인 성공")
                fetch_and_save(mb)
            print(f"[email_daemon] 다음 폴링까지 {POLL_INTERVAL}초 대기")
            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            print("[email_daemon] 종료")
            break
        except Exception as e:
            print(f"[email_daemon] 에러: {e}, {RETRY_DELAY}초 후 재시도")
            time.sleep(RETRY_DELAY)


if __name__ == "__main__":
    run()

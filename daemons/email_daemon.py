"""네이버 이메일 IMAP 폴링 데몬 — 최근 메일 수집 → data/email.json."""

import json
import os
import re
import sys
from datetime import datetime

from imap_tools import MailBox, AND

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from monitor_base import MonitorBase

EMAIL = os.environ.get("NAVER_EMAIL", "")
PASSWORD = os.environ.get("NAVER_APP_PASSWORD", "")
IMAP_HOST = "imap.naver.com"
FETCH_COUNT = 10


class EmailDaemon(MonitorBase):
    name = "email"
    interval = 300

    def on_start(self):
        if not EMAIL or not PASSWORD:
            self.log("NAVER_EMAIL / NAVER_APP_PASSWORD 미설정")
            sys.exit(1)
        self.data_dir = self.root / "data"
        self.emails_dir = self.data_dir / "emails"
        self.json_path = self.data_dir / "email.json"

    def check(self):
        with MailBox(IMAP_HOST).login(EMAIL, PASSWORD) as mb:
            msgs = list(mb.fetch(AND(all=True), limit=FETCH_COUNT, reverse=True))

        self.emails_dir.mkdir(parents=True, exist_ok=True)
        items = []
        for m in msgs:
            body_text = m.text or (_strip_html(m.html) if m.html else "")
            preview = body_text[:200].replace("\n", " ").strip()

            (self.emails_dir / f"{m.uid}.txt").write_text(
                f"From: {m.from_}\nSubject: {m.subject}\nDate: {m.date}\n\n"
                + (body_text or "(본문 없음)"),
                encoding="utf-8",
            )

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
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.json_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8",
        )
        return f"{len(items)}건 저장"


def _strip_html(html):
    text = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


if __name__ == "__main__":
    EmailDaemon().run()

"""트럼프 Truth Social RSS 모니터 — 키워드 필터 + claude 판단 후 iMessage 알림.

RSS 소스: https://www.trumpstruth.org/feed
동작: 5분 간격 폴링 → 키워드 pre-filter → claude -p 이란전 중요도 판단
      → important=true면 해설 포함 outbox JSON → alf_bridge가 iMessage 발신
"""

import re
import sys

import feedparser

sys.path.insert(0, __import__("pathlib").Path(__file__).resolve().parent.parent.joinpath("src").__str__())
from monitor_base import MonitorBase

FEED_URL = "https://www.trumpstruth.org/feed"

KEYWORDS = {
    "iran": [
        "iran", "iranian", "tehran", "khamenei",
        "nuclear deal", "enrichment", "uranium", "centrifuge",
        "strait of hormuz", "hormuz", "persian gulf",
        "ceasefire", "bombing iran",
    ],
    "tariff": [
        "tariff", "tariffs",
        "trade war", "trade deal", "trade deficit",
        "reciprocal tax", "import tax", "duties",
    ],
    "market": [
        "stock market", "dow jones", "nasdaq", "s&p 500",
        "federal reserve", "interest rate",
        "recession", "oil price", "crude oil",
    ],
    "china": [
        "china", "chinese", "xi jinping", "beijing",
        "south china sea", "taiwan",
    ],
    "korea": [
        "korea", "korean", "south korea",
        "kim jong", "north korea", "dprk",
        "samsung", "hyundai",
    ],
}

_ALL_KW = []
for words in KEYWORDS.values():
    _ALL_KW.extend(words)
_PATTERN = re.compile("|".join(re.escape(kw) for kw in _ALL_KW), re.IGNORECASE)

SYSTEM_PROMPT = """\
너는 이란전(이란 vs 이스라엘/미국 충돌) 전문 분석가다.
트럼프 대통령의 Truth Social 포스트가 이란전과 관련된 중요 정보인지 판단한다.

## 판단 기준
- important=true: 이란에 대한 군사행동·위협·협상·제재, 호르무즈 해협, 핵 프로그램·우라늄 농축,
  이란 지도부(하메네이 등), 이스라엘-이란 충돌, 미군 중동 배치/철수, 휴전/출구전략 등
  이란전 향방에 실질 영향을 줄 수 있는 내용
- important=false: 이란 단어만 스치듯 언급되거나, 이란전과 무관한 관세·국내정치·일상 포스트,
  과거 치적 자랑 등

## 출력 형식 (반드시 JSON만, 코드펜스/설명 금지)
{"important": true, "severity": "긴급|주의|참고", "commentary": "한국어 3~5줄 해설"}

- commentary: 왜 중요한지, 맥락, 시장/외교 영향을 3~5줄로 간결하게
- important=false면 severity="참고", commentary=""
"""


class TrumpMonitor(MonitorBase):
    name = "trump"
    interval = 300
    claude_model = "sonnet"
    claude_system_prompt = SYSTEM_PROMPT

    def on_start(self):
        self._state_file = self.root / "run" / "trump_last_id.txt"
        self.log(f"키워드 카테고리: {', '.join(KEYWORDS.keys())} ({len(_ALL_KW)}개)")
        self.log(f"수신자: {self.recipient or '(미설정, 콘솔 출력)'}")
        # 첫 실행 시 현재 위치 기록 (과거 포스트 알림 방지)
        if not self._state_file.exists():
            entries = self._fetch_feed()
            if entries:
                first_id = entries[0].get("truth_originalid") or entries[0].get("id", "")
                self._save_last_id(first_id)
                self.log(f"초기화: last_id={first_id}")

    def check(self):
        entries = self._fetch_feed()
        if not entries:
            return "피드 없음"

        new_entries = self._filter_new(entries)
        if not new_entries:
            return "신규 없음"

        # 최신 ID 저장
        self._save_last_id(new_entries[0][1])

        alerts = judged = 0
        for entry, _ in reversed(new_entries):
            title = entry.get("title", "")
            desc = entry.get("description", "")

            if title.startswith("RT @"):
                continue

            if not self._keyword_match(f"{title} {desc}"):
                self.log(f"skip(no keyword): {title[:60]}")
                continue

            judged += 1
            verdict = self.ask_claude(self._build_prompt(title, desc))
            if verdict is None:
                self.log(f"skip(claude failed): {title[:60]}")
                continue
            if not isinstance(verdict, dict) or not verdict.get("important"):
                self.log(f"skip(not important): {title[:60]}")
                continue

            self.write_outbox(self._format_alert(entry, verdict))
            self.log(f"ALERT [{verdict.get('severity', '?')}] {title[:60]}")
            alerts += 1

        return f"{len(new_entries)}건 중 {judged}판단, {alerts}알림"

    # ── private ───────────────────────────────────────

    def _fetch_feed(self):
        feed = feedparser.parse(FEED_URL)
        if feed.bozo and not feed.entries:
            self.log(f"피드 파싱 오류: {feed.bozo_exception}")
            return []
        return feed.entries

    def _filter_new(self, entries):
        last_id = self._state_file.read_text().strip() if self._state_file.exists() else None
        new = []
        for entry in entries:
            post_id = entry.get("truth_originalid") or entry.get("id") or entry.get("link", "")
            if post_id == last_id:
                break
            new.append((entry, post_id))
        return new

    def _keyword_match(self, text):
        return bool(_PATTERN.search(text))

    def _build_prompt(self, title, desc):
        clean = re.sub(r"<[^>]+>", " ", desc or "")[:2000]
        return f"다음 트럼프 Truth Social 포스트를 이란전 관점에서 판단해줘.\n\n제목: {title}\n\n본문: {clean}\n\nJSON만 출력."

    def _format_alert(self, entry, verdict):
        title = entry.get("title", "").strip()
        link = entry.get("link", "")
        pub = entry.get("published", "")
        severity = verdict.get("severity", "참고")
        commentary = (verdict.get("commentary") or "").strip()

        lines = [
            f"[Trump|{severity}] 이란전",
            "",
            "== 해설 ==",
            commentary or "(해설 없음)",
            "",
            "== 원문 ==",
            title[:500],
            "",
            link,
        ]
        if pub:
            lines.append(f"({pub})")
        return "\n".join(lines)

    def _save_last_id(self, post_id):
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._state_file.write_text(str(post_id))


if __name__ == "__main__":
    TrumpMonitor().run()

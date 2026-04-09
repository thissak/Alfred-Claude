#!/usr/bin/env python3
"""트럼프 Truth Social RSS 모니터 — 키워드 필터 + claude 판단 후 iMessage 알림.

RSS 소스: https://www.trumpstruth.org/feed
동작: 5분 간격 폴링 → 키워드 pre-filter → claude -p 이란전 중요도 판단
      → important=true면 해설 포함 outbox JSON → alf_bridge가 iMessage 발신

사용법:
  python daemons/trump_monitor.py              # 데몬 모드
  TRUMP_RUN_NOW=1 python daemons/trump_monitor.py  # 즉시 1회 실행 (테스트)

환경변수:
  ALF_MY_NUMBER   — iMessage 수신자 (필수)
  TRUMP_INTERVAL  — 폴링 간격 초 (기본 300)
  TRUMP_RUN_NOW   — 1이면 즉시 1회 실행 후 종료
"""

import json
import os
import re
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

import feedparser

ROOT = Path(__file__).resolve().parent.parent
OUTBOX = ROOT / "run" / "outbox"
STATE_FILE = ROOT / "run" / "trump_last_id.txt"

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

sys.path.insert(0, str(ROOT / "src"))
from heartbeat import beat

RECIPIENT = os.environ.get("ALF_MY_NUMBER", "")
POLL_INTERVAL = int(os.environ.get("TRUMP_INTERVAL", "300"))
FEED_URL = "https://www.trumpstruth.org/feed"
CLAUDE_CLI = "/Users/afred/.local/bin/claude"

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

# ── 키워드 필터 ────────────────────────────────────────
# 카테고리별 키워드. 하나라도 매칭되면 알림.

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

# 모든 키워드를 하나의 패턴으로 컴파일
_ALL_KEYWORDS = []
for cat_words in KEYWORDS.values():
    _ALL_KEYWORDS.extend(cat_words)
_PATTERN = re.compile("|".join(re.escape(kw) for kw in _ALL_KEYWORDS), re.IGNORECASE)


def log(msg):
    print(f"[trump {datetime.now():%H:%M:%S}] {msg}", flush=True)


# ── 상태 관리 ──────────────────────────────────────────

def load_last_id():
    """마지막으로 처리한 포스트 ID."""
    if STATE_FILE.exists():
        return STATE_FILE.read_text().strip()
    return None


def save_last_id(post_id):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(post_id)


# ── 피드 처리 ──────────────────────────────────────────

def fetch_feed():
    """RSS 피드 파싱. Returns: list of entries (최신순)."""
    feed = feedparser.parse(FEED_URL)
    if feed.bozo and not feed.entries:
        log(f"피드 파싱 오류: {feed.bozo_exception}")
        return []
    return feed.entries


def match_keywords(text):
    """텍스트에서 매칭되는 키워드 카테고리 반환."""
    matches = _PATTERN.findall(text.lower())
    if not matches:
        return []

    categories = set()
    text_lower = text.lower()
    for cat, words in KEYWORDS.items():
        for w in words:
            if w.lower() in text_lower:
                categories.add(cat)
                break
    return sorted(categories)


def strip_html(text):
    """description의 HTML 태그 제거 (claude 프롬프트용)."""
    return re.sub(r"<[^>]+>", " ", text or "")


# ── Claude 판단 ────────────────────────────────────────

def ask_claude(title, desc):
    """claude -p로 이란전 중요도 판단. Returns: dict 또는 None."""
    clean_desc = strip_html(desc)[:2000]
    prompt = f"""\
다음 트럼프 Truth Social 포스트를 이란전 관점에서 판단해줘.

제목: {title}

본문: {clean_desc}

JSON만 출력."""

    env = os.environ.copy()
    env.pop("CLAUDECODE", None)

    cmd = [
        CLAUDE_CLI, "-p",
        "--model", "sonnet",
        "--output-format", "json",
        "--max-turns", "1",
        "--allowedTools", "",
        "--system-prompt", SYSTEM_PROMPT,
        prompt,
    ]
    log("claude -p 판단 시작...")

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120, env=env,
        )
        if result.returncode != 0:
            log(f"claude 에러: {result.stderr.strip()[:200]}")
            return None
        outer = json.loads(result.stdout)
        raw = (outer.get("result") or "").strip()
        # 코드펜스 방어
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.DOTALL).strip()
        verdict = json.loads(raw)
        return verdict
    except (subprocess.TimeoutExpired, json.JSONDecodeError, KeyError) as e:
        log(f"claude 실패: {e}")
        return None


def format_alert(entry, verdict):
    """알림 메시지 포맷 — claude 해설 포함."""
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


def write_outbox(message):
    """outbox JSON 생성 → alf_bridge가 iMessage 발신."""
    if not RECIPIENT:
        log("ALF_MY_NUMBER 미설정, 콘솔 출력만")
        print(message)
        return

    OUTBOX.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    payload = {
        "recipient": RECIPIENT,
        "message": message,
        "timestamp": datetime.now().isoformat(),
    }
    path = OUTBOX / f"trump_{ts}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    log(f"outbox: {path.name}")


# ── 메인 체크 ──────────────────────────────────────────

def check_feed():
    """피드 체크 1회. Returns: 새 알림 수."""
    entries = fetch_feed()
    if not entries:
        return 0

    last_id = load_last_id()
    new_entries = []

    for entry in entries:
        # truth:originalId 또는 guid 사용
        post_id = entry.get("truth_originalid") or entry.get("id") or entry.get("link", "")
        if post_id == last_id:
            break
        new_entries.append((entry, post_id))

    if not new_entries:
        return 0

    # 최신 ID 저장 (첫 번째 = 가장 최신)
    save_last_id(new_entries[0][1])

    # 오래된 것부터 처리 (시간순 알림)
    alerts = 0
    judged = 0
    for entry, post_id in reversed(new_entries):
        title = entry.get("title", "")
        desc = entry.get("description", "")
        full_text = f"{title} {desc}"

        # RT 중복 제외
        if title.startswith("RT @"):
            continue

        # 1단계: 키워드 pre-filter
        categories = match_keywords(full_text)
        if not categories:
            log(f"skip(no keyword): {title[:60]}")
            continue

        # 2단계: claude 이란전 중요도 판단
        judged += 1
        verdict = ask_claude(title, desc)
        if verdict is None:
            log(f"skip(claude failed): {title[:60]}")
            continue

        if not verdict.get("important"):
            log(f"skip(not important): {title[:60]}")
            continue

        msg = format_alert(entry, verdict)
        write_outbox(msg)
        log(f"ALERT [{verdict.get('severity', '?')}] {title[:60]}")
        alerts += 1

    log(f"체크 완료: {len(new_entries)}건 중 {judged}건 판단, {alerts}건 알림")
    return alerts


# ── 데몬 루프 ──────────────────────────────────────────

def run():
    log(f"트럼프 모니터 시작 (interval={POLL_INTERVAL}s)")
    log(f"키워드 카테고리: {', '.join(KEYWORDS.keys())} ({len(_ALL_KEYWORDS)}개)")
    log(f"수신자: {RECIPIENT or '(미설정, 콘솔 출력)'}")

    beat("trump", "ok", "시작됨")

    # 즉시 실행 모드
    if os.environ.get("TRUMP_RUN_NOW") == "1":
        check_feed()
        beat("trump", "ok", "즉시 실행 완료")
        return

    # 첫 실행 시 현재 위치만 기록 (과거 포스트 알림 방지)
    if not STATE_FILE.exists():
        entries = fetch_feed()
        if entries:
            first_id = entries[0].get("truth_originalid") or entries[0].get("id", "")
            save_last_id(first_id)
            log(f"초기화: last_id={first_id}")

    while True:
        try:
            n = check_feed()
            beat("trump", "ok", f"체크 완료 ({n}건 알림)")
            time.sleep(POLL_INTERVAL)
        except KeyboardInterrupt:
            log("종료")
            break
        except Exception as e:
            beat("trump", "error", str(e)[:100])
            log(f"에러: {e}")
            traceback.print_exc()
            time.sleep(60)


if __name__ == "__main__":
    run()

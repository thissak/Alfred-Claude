#!/usr/bin/env python3
"""장중 급등/급락 모니터 — 등락률순위 폴링 → 뉴스 수집 → Claude 분석 → iMessage 발송.

평일 09:00~15:30, 5분 간격으로 등락률순위 API를 폴링.
신규 급등(+5%)/급락(-5%) 감지 시 뉴스 조회 후 claude -p로 분석, outbox에 드롭.

환경변수:
  INTRADAY_INTERVAL=300    폴링 간격(초, 기본 300)
  INTRADAY_MIN_RETURN=5.0  감지 임계값(%, 기본 5.0)
  INTRADAY_RUN_NOW=1       즉시 1회 실행(테스트용)
"""

import json
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

os.environ.setdefault("KIS_THROTTLE", "0.5")

sys.path.insert(0, os.path.join(ROOT, "scripts"))

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))

from scan_surge import _fetch_fluctuation_rank, fetch_news, _pick_best_news

OUTBOX = os.path.join(ROOT, "run", "outbox")
INTERVAL = int(os.environ.get("INTRADAY_INTERVAL", "300"))
MIN_RETURN = float(os.environ.get("INTRADAY_MIN_RETURN", "5.0"))


def log(msg):
    print(f"[intraday {datetime.now():%H:%M:%S}] {msg}", flush=True)


def fetch_fluctuation_rank_drop(min_drop=5.0):
    """등락률순위 (하락) 조회."""
    from kis_readonly_client import get as kis_get
    data = kis_get(
        "/uapi/domestic-stock/v1/ranking/fluctuation",
        "FHPST01700000",
        {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_COND_SCR_DIV_CODE": "20170",
            "FID_INPUT_ISCD": "0000",
            "FID_RANK_SORT_CLS_CODE": "1",     # 1=하락률
            "FID_INPUT_CNT_1": "0",
            "FID_PRC_CLS_CODE": "1",
            "FID_INPUT_PRICE_1": "",
            "FID_INPUT_PRICE_2": "",
            "FID_VOL_CNT": "",
            "FID_TRGT_CLS_CODE": "0",
            "FID_TRGT_EXLS_CLS_CODE": "0",
            "FID_DIV_CLS_CODE": "0",
            "FID_RSFL_RATE1": "",
            "FID_RSFL_RATE2": str(-min_drop),
        },
    )
    if not data:
        return []

    results = []
    for item in data.get("output", []):
        code = item.get("mksc_shrn_iscd") or item.get("stck_shrn_iscd", "")
        name = item.get("hts_kor_isnm", "")
        rate = item.get("prdy_ctrt", "0")
        vol = item.get("acml_vol", "0")
        if not code:
            continue
        try:
            rate_f = float(rate)
        except ValueError:
            continue
        if rate_f > -min_drop:
            continue
        results.append({
            "code": code,
            "name": name,
            "return_1d": round(rate_f, 2),
            "volume": int(vol) if vol else 0,
        })
    return results


def collect_alerts(seen):
    """급등 + 급락 종목 수집. 이미 본 종목은 제외."""
    date_str = datetime.now().strftime("%Y-%m-%d")

    surges = _fetch_fluctuation_rank(MIN_RETURN)
    drops = fetch_fluctuation_rank_drop(MIN_RETURN)

    new_alerts = []
    for s in surges + drops:
        key = (s["code"], date_str)
        if key in seen:
            continue

        news_list = fetch_news(s["code"])
        best = _pick_best_news(news_list)

        s["news_title"] = best["title"] if best else "-"
        s["news_source"] = best["source"] if best else "-"
        new_alerts.append(s)
        seen.add(key)

    return new_alerts


def build_prompt(alerts, date_str):
    """Claude 분석용 프롬프트 생성."""
    lines = []
    for i, a in enumerate(alerts, 1):
        sign = "+" if a["return_1d"] > 0 else ""
        lines.append(f"{i}. {a['name']} ({a['code']}) {sign}{a['return_1d']}%")
        lines.append(f"   뉴스: {a['news_title']}")

    return f"""아래는 {date_str} 장중 급등/급락 종목이야.
각 종목이 왜 움직였는지 뉴스 근거로 1~2문장 분석해줘.
투자 의견 빼고 팩트만. iMessage로 보낼거라 간결하게.

{chr(10).join(lines)}"""


def analyze_with_claude(prompt):
    """claude -p로 분석 실행."""
    result = subprocess.run(
        ["claude", "-p", "--model", "sonnet"],
        input=prompt, capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        log(f"claude 에러: {result.stderr[:200]}")
        return None
    return result.stdout.strip()


def send_to_outbox(text):
    """outbox에 JSON 드롭 → bridge가 iMessage 발송."""
    os.makedirs(OUTBOX, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(OUTBOX, f"intraday_{ts}.json")
    with open(path, "w") as f:
        json.dump({"message": text}, f, ensure_ascii=False)
    log(f"outbox 발송: {path}")


def run_once(seen):
    """1회 스캔 → 분석 → 발송."""
    alerts = collect_alerts(seen)
    if not alerts:
        log(f"신규 감지 없음 (누적 {len(seen)}종목 감시 중)")
        return

    date_str = datetime.now().strftime("%Y-%m-%d")
    direction = []
    up = [a for a in alerts if a["return_1d"] > 0]
    down = [a for a in alerts if a["return_1d"] < 0]
    if up:
        direction.append(f"급등 {len(up)}")
    if down:
        direction.append(f"급락 {len(down)}")
    log(f"신규 감지: {', '.join(direction)}종목")

    prompt = build_prompt(alerts, date_str)
    analysis = analyze_with_claude(prompt)
    if not analysis:
        return

    send_to_outbox(analysis)


def run():
    log(f"장중 모니터 시작 (interval={INTERVAL}s, min_return={MIN_RETURN}%)")
    seen = set()

    if os.environ.get("INTRADAY_RUN_NOW") == "1":
        run_once(seen)
        return

    while True:
        try:
            now = datetime.now()
            h = now.hour * 100 + now.minute

            if now.weekday() >= 5:
                log("주말. 대기.")
                time.sleep(3600)
                continue

            if h < 900:
                log(f"장 시작 전 ({now:%H:%M}). 대기.")
                time.sleep(60)
                continue

            if h > 1530:
                log("장 마감. 내일까지 대기.")
                seen.clear()
                # 다음 날 08:50까지 sleep
                import datetime as dt_mod
                tomorrow_9 = datetime(now.year, now.month, now.day, 8, 50)
                if tomorrow_9 <= now:
                    tomorrow_9 += dt_mod.timedelta(days=1)
                sleep_sec = (tomorrow_9 - now).total_seconds()
                time.sleep(max(sleep_sec, 60))
                continue

            run_once(seen)
            time.sleep(INTERVAL)

        except KeyboardInterrupt:
            log("종료")
            break
        except Exception as e:
            log(f"에러: {e}")
            traceback.print_exc()
            time.sleep(60)


if __name__ == "__main__":
    run()

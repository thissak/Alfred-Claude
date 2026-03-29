#!/usr/bin/env python3
"""급등 뉴스 스크리닝 — daily_screening에서 급등 종목 추출 + 뉴스 API 조합.

사용법:
  # EOD 스크리닝 (오늘 기준)
  python scripts/scan_surge.py

  # 특정 날짜
  python scripts/scan_surge.py --date 2026-03-27

  # 장중 실시간 (등락률순위 API → 뉴스 조회)
  python scripts/scan_surge.py --live

  # 임계값 조정
  python scripts/scan_surge.py --min-return 10 --min-vol-ratio 2.0
"""

import argparse
import os
import sys
import time
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

os.environ.setdefault("KIS_THROTTLE", "0.5")

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))

import market_db as db
from kis_readonly_client import get as kis_get


def log(msg):
    print(f"[surge {datetime.now():%H:%M:%S}] {msg}", flush=True)


# ── 뉴스 조회 ─────────────────────────────────────────

def fetch_news(code, date_str=""):
    """종목 뉴스 제목 조회. Returns: list of {title, source, time}."""
    date_fmt = date_str.replace("-", "") if date_str else ""
    data = kis_get(
        "/uapi/domestic-stock/v1/quotations/news-title",
        "FHKST01011800",
        {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_COND_MRKT_CLS_CODE": "",
            "FID_INPUT_ISCD": code,
            "FID_INPUT_DATE_1": date_fmt,
            "FID_INPUT_DATE_2": "",
            "FID_NEWS_OFER_ENTP_CODE": "",
            "FID_TITL_CNTT": "",
            "FID_INPUT_HOUR_1": "",
            "FID_RANK_SORT_CLS_CODE": "0",
            "FID_INPUT_SRNO": "",
        },
    )
    if not data:
        return []

    results = []
    for item in data.get("output", []):
        title = item.get("hts_pbnt_titl_cntt", "")
        source = item.get("dorg", "")
        tm = item.get("data_tm", "")
        dt = item.get("data_dt", "")
        # 해당 종목이 주인공인 뉴스만 필터 (iscd1이 해당 종목)
        if item.get("iscd1") == code:
            time_str = f"{tm[:2]}:{tm[2:4]}:{tm[4:6]}" if len(tm) >= 6 else tm
            results.append({
                "title": title,
                "source": source,
                "time": time_str,
                "date": f"{dt[:4]}-{dt[4:6]}-{dt[6:8]}" if len(dt) == 8 else dt,
            })
    return results


def _pick_best_news(news_list):
    """뉴스 중 가장 의미 있는 것 선택 (인포스탁 순위류 제외 우선)."""
    # 순위/상위 등 기계적 뉴스 제외
    noise_keywords = ["상위", "하위", "종목(", "상승률", "하락률", "거래량"]
    meaningful = [
        n for n in news_list
        if not any(kw in n["title"] for kw in noise_keywords)
    ]
    if meaningful:
        return meaningful[0]
    return news_list[0] if news_list else None


# ── 1. EOD 스크리닝 (DB 기반) ──────────────────────────

def scan_eod(date_str, min_return=5.0, min_vol_ratio=1.5):
    """daily_screening 기반 급등 종목 추출 + 뉴스 보강."""
    db.init()

    surges = db.get_screening(
        date_str,
        filters={
            "return_1d": (">=", min_return),
            "volume_ratio_5d": (">=", min_vol_ratio),
        },
        sort_by="return_1d",
        ascending=False,
        limit=50,
    )

    if not surges:
        log(f"급등 종목 없음 (date={date_str}, return>={min_return}%, vol_ratio>={min_vol_ratio})")
        return []

    log(f"급등 후보 {len(surges)}종목, 뉴스 조회 중...")

    alerts = []
    for s in surges:
        news_list = fetch_news(s["code"], date_str)
        best = _pick_best_news(news_list)

        alert = {
            "code": s["code"],
            "date": date_str,
            "close": s["close"],
            "return_1d": round(s["return_1d"], 2),
            "volume_ratio": s.get("volume_ratio_5d"),
            "mktcap": s.get("mktcap"),
            "foreign_net_5d": s.get("foreign_net_5d"),
            "news_title": best["title"] if best else None,
            "news_source": best["source"] if best else None,
            "news_time": best["time"] if best else None,
        }
        alerts.append(alert)

    # DB 저장
    if alerts:
        n = db.upsert_surge_alerts(alerts)
        log(f"surge_alerts 저장: {n}건")

    return alerts


# ── 2. 장중 실시간 (등락률순위 API) ────────────────────

def scan_live(min_return=5.0, interval=300):
    """등락률순위 API → 급등 종목 → 뉴스 조회. interval초 간격 반복."""
    db.init()
    log(f"장중 실시간 모니터링 시작 (interval={interval}s, min_return={min_return}%)")

    seen = set()  # 중복 알림 방지

    while True:
        try:
            now = datetime.now()
            h = now.hour * 100 + now.minute

            # 장 시간 체크 (09:00 ~ 15:30)
            if h < 900 or h > 1530:
                if h > 1530:
                    log("장 마감. 종료.")
                    break
                log(f"장 시작 전 ({now:%H:%M}). 대기 중...")
                time.sleep(60)
                continue

            # 등락률순위 (상승) 조회
            surges = _fetch_fluctuation_rank(min_return)
            date_str = now.strftime("%Y-%m-%d")

            new_alerts = []
            for s in surges:
                key = (s["code"], date_str)
                if key in seen:
                    continue

                news_list = fetch_news(s["code"])
                best = _pick_best_news(news_list)

                alert = {
                    "code": s["code"],
                    "name": s["name"],
                    "return_1d": s["return_1d"],
                    "volume": s.get("volume"),
                    "news_title": best["title"] if best else "-",
                    "news_source": best["source"] if best else "-",
                }
                new_alerts.append(alert)
                seen.add(key)

            if new_alerts:
                _print_live_alerts(new_alerts)

            time.sleep(interval)

        except KeyboardInterrupt:
            log("종료")
            break


def _fetch_fluctuation_rank(min_return=5.0):
    """등락률순위 API → 상승 상위 종목."""
    data = kis_get(
        "/uapi/domestic-stock/v1/ranking/fluctuation",
        "FHPST01700000",
        {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_COND_SCR_DIV_CODE": "20170",
            "FID_INPUT_ISCD": "0000",
            "FID_RANK_SORT_CLS_CODE": "0",     # 0=상승률
            "FID_INPUT_CNT_1": "0",
            "FID_PRC_CLS_CODE": "1",            # 1=보통주
            "FID_INPUT_PRICE_1": "",
            "FID_INPUT_PRICE_2": "",
            "FID_VOL_CNT": "",
            "FID_TRGT_CLS_CODE": "0",
            "FID_TRGT_EXLS_CLS_CODE": "0",
            "FID_DIV_CLS_CODE": "0",
            "FID_RSFL_RATE1": str(min_return),
            "FID_RSFL_RATE2": "",
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
        if rate_f < min_return:
            continue
        results.append({
            "code": code,
            "name": name,
            "return_1d": round(rate_f, 2),
            "volume": int(vol) if vol else 0,
        })
    return results


def _print_live_alerts(alerts):
    """장중 알림 출력."""
    print()
    print(f"{'='*70}")
    print(f"  급등 감지 — {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"{'='*70}")
    for a in alerts:
        news = a["news_title"][:40] if a["news_title"] else "-"
        print(f"  {a['name']:12s} ({a['code']})  +{a['return_1d']:5.1f}%  "
              f"vol={a['volume']:>12,}  {a['news_source']:6s} {news}")
    print(f"{'='*70}")
    print()


# ── 3. 출력 포맷 ──────────────────────────────────────

def print_eod_report(alerts):
    """EOD 스크리닝 결과 출력."""
    if not alerts:
        return

    conn = db._get_conn()
    print()
    print(f"{'='*80}")
    print(f"  급등 뉴스 스크리닝 리포트 — {alerts[0]['date']}")
    print(f"{'='*80}")
    print(f"  {'종목':10s} {'코드':8s} {'등락':>6s} {'거래비':>6s} "
          f"{'시총(억)':>9s} {'외인5d':>8s}  뉴스")
    print(f"  {'-'*74}")

    for a in alerts:
        name_row = conn.execute(
            "SELECT name FROM securities WHERE code=?", (a["code"],)
        ).fetchone()
        name = name_row["name"] if name_row else a["code"]

        news = a.get("news_title") or "-"
        if len(news) > 35:
            news = news[:35] + "…"
        src = a.get("news_source") or ""

        mktcap_str = f"{a['mktcap']:>9,}" if a.get("mktcap") else "        -"
        frgn_str = f"{a['foreign_net_5d']:>8,}" if a.get("foreign_net_5d") else "       -"
        vol_str = f"{a['volume_ratio']:>5.1f}x" if a.get("volume_ratio") else "     -"

        print(f"  {name:10s} {a['code']:8s} +{a['return_1d']:5.1f}% {vol_str} "
              f"{mktcap_str} {frgn_str}  [{src}] {news}")

    print(f"{'='*80}")
    print()


# ── main ───────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="급등 뉴스 스크리닝")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--min-return", type=float, default=5.0)
    parser.add_argument("--min-vol-ratio", type=float, default=1.5)
    parser.add_argument("--live", action="store_true", help="장중 실시간 모니터링")
    parser.add_argument("--interval", type=int, default=300, help="실시간 조회 간격(초)")
    args = parser.parse_args()

    if args.live:
        scan_live(min_return=args.min_return, interval=args.interval)
    else:
        alerts = scan_eod(args.date, args.min_return, args.min_vol_ratio)
        print_eod_report(alerts)


if __name__ == "__main__":
    main()

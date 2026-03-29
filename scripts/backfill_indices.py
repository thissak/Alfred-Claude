#!/usr/bin/env python3
"""시장 지수 5년 백필 — 네이버 금융 API.

사용법:
  python3 scripts/backfill_indices.py                    # 최근 5년
  python3 scripts/backfill_indices.py --start 2024-01-01  # 특정 시작일
  python3 scripts/backfill_indices.py --months 6          # 최근 6개월
"""

import argparse
import os
import re
import sys
import time
from datetime import datetime, timedelta

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import market_db as db

INDICES = [
    ("KOSPI", "0001", "KOSPI"),
    ("KOSDAQ", "1001", "KOSDAQ"),
    ("KPI200", "2001", "KOSPI200"),
]


def log(msg):
    print(f"[backfill-idx {datetime.now():%H:%M:%S}] {msg}", flush=True)


def fetch_naver_index(symbol, start, end):
    """네이버 금융에서 지수 일별 시세 조회. Returns: list of tuples."""
    url = "https://fchart.stock.naver.com/siseJson.nhn"
    params = {
        "symbol": symbol,
        "requestType": 1,
        "startTime": start.replace("-", ""),
        "endTime": end.replace("-", ""),
        "timeframe": "day",
    }
    r = requests.get(url, params=params, headers={"User-Agent": "Mozilla/5.0"})
    if r.status_code != 200:
        return []

    # 응답 파싱: JS 배열 형태 → 정규식으로 행 추출
    rows = []
    for m in re.finditer(
        r'\["(\d{8})",\s*([\d.]+),\s*([\d.]+),\s*([\d.]+),\s*([\d.]+),\s*(\d+)',
        r.text,
    ):
        date_raw, open_, high, low, close, volume = m.groups()
        date_str = f"{date_raw[:4]}-{date_raw[4:6]}-{date_raw[6:8]}"
        rows.append({
            "date": date_str,
            "open": float(open_),
            "high": float(high),
            "low": float(low),
            "close": float(close),
            "volume": int(volume),
        })
    return rows


def backfill_indices(start_date, end_date):
    """지수 백필 메인."""
    db.init()
    total = 0

    for symbol, code, name in INDICES:
        log(f"{name} 수집 중...")
        raw = fetch_naver_index(symbol, start_date, end_date)
        if not raw:
            log(f"  {name}: 데이터 없음")
            continue

        rows = []
        prev_close = None
        for r in raw:
            change = round(r["close"] - prev_close, 2) if prev_close else None
            change_rate = (
                round((r["close"] / prev_close - 1) * 100, 2)
                if prev_close
                else None
            )
            rows.append({
                "code": code,
                "name": name,
                "date": r["date"],
                "close": r["close"],
                "change": change,
                "change_rate": change_rate,
                "volume": r["volume"],
                "trade_value": None,
            })
            prev_close = r["close"]

        n = db.upsert_daily_indices(rows)
        log(f"  {name}: {n}건 ({rows[0]['date']} ~ {rows[-1]['date']})")
        total += n
        time.sleep(1)

    log(f"=== 지수 백필 완료: {total}건 ===")
    return total


def main():
    parser = argparse.ArgumentParser(description="시장 지수 백필")
    parser.add_argument("--start", help="시작일 (YYYY-MM-DD)")
    parser.add_argument(
        "--end", default=datetime.now().strftime("%Y-%m-%d"), help="종료일"
    )
    parser.add_argument(
        "--months", type=int, default=60, help="최근 N개월 (start 미지정 시)"
    )
    args = parser.parse_args()

    if not args.start:
        start = (datetime.now() - timedelta(days=args.months * 30)).strftime(
            "%Y-%m-%d"
        )
    else:
        start = args.start

    log(f"백필 범위: {start} ~ {args.end}")
    backfill_indices(start, args.end)


if __name__ == "__main__":
    main()

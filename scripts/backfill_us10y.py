#!/usr/bin/env python3
"""미국 10년물 국채금리(^TNX) 일봉 → daily_indices(code='US10Y') 백필.

야후 파이낸스 chart API에서 일봉 전체(1970~)를 받아 저장한다.
change/change_rate는 직전 거래일 대비로 계산. volume/trade_value는 없음(None).

사용법:
  python3 scripts/backfill_us10y.py                 # 전체 (1970~)
  python3 scripts/backfill_us10y.py --start 2000-01-01
"""

import argparse
import os
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import market_db as db
import treasury_yield as ty

CODE = "US10Y"
NAME = "미국 10년물 국채"


def log(msg):
    print(f"[us10y {datetime.now():%H:%M:%S}] {msg}", flush=True)


def backfill(start=None):
    hist = ty.fetch_history()
    if not hist:
        log("야후 ^TNX 조회 실패 — 백필 중단")
        return 0
    if start:
        hist = [(d, c) for d, c in hist if d >= start]
    if not hist:
        log("해당 기간 데이터 없음")
        return 0

    rows = []
    prev = None
    for d, c in hist:
        change = round(c - prev, 4) if prev is not None else None
        rate = round((c - prev) / prev * 100, 4) if prev else None
        rows.append({
            "code": CODE, "name": NAME, "date": d, "close": c,
            "change": change, "change_rate": rate,
            "volume": None, "trade_value": None,
        })
        prev = c

    db.init()
    n = db.upsert_daily_indices(rows)
    log(f"=== US10Y 백필 완료: {n}건 ({hist[0][0]} ~ {hist[-1][0]}, 최신 {hist[-1][1]}%) ===")
    return n


def main():
    ap = argparse.ArgumentParser(description="미국 10년물 국채금리 백필")
    ap.add_argument("--start", help="시작일 YYYY-MM-DD (기본: 전체 1970~)")
    args = ap.parse_args()
    backfill(start=args.start)


if __name__ == "__main__":
    main()

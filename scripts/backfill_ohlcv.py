#!/usr/bin/env python3
"""PyKRX 과거 OHLCV 백필 — 종목별 시계열 적재.

사용법:
  python3 scripts/backfill_ohlcv.py                    # 최근 5년
  python3 scripts/backfill_ohlcv.py --start 2024-01-01  # 특정 시작일
  python3 scripts/backfill_ohlcv.py --months 6          # 최근 6개월
  python3 scripts/backfill_ohlcv.py --skip-ohlcv        # 펀더멘탈만
"""

import argparse
import os
import sys
import time
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import market_db as db
from pykrx import stock as krx


def log(msg):
    print(f"[backfill {datetime.now():%H:%M:%S}] {msg}", flush=True)


def backfill_ohlcv(start_date: str, end_date: str):
    """종목별로 기간 OHLCV 수집 → daily_prices 적재."""
    db.init()

    s = start_date.replace("-", "")
    e = end_date.replace("-", "")

    codes = db.get_all_codes()
    if not codes:
        log("securities 테이블이 비어있음. collector를 먼저 실행하세요.")
        return 0

    log(f"OHLCV 백필: {len(codes)}종목, {start_date} ~ {end_date}")
    total_rows = 0
    errors = 0

    for i, code in enumerate(codes):
        try:
            df = krx.get_market_ohlcv_by_date(s, e, code)
        except Exception as ex:
            errors += 1
            if errors % 50 == 0:
                log(f"  에러 누적 {errors}건: {ex}")
            time.sleep(1)
            continue

        if df.empty:
            continue

        rows = []
        for date_idx, row in df.iterrows():
            date_str = date_idx.strftime("%Y-%m-%d")
            close = int(row.get("종가", 0))
            if close == 0:
                continue
            rows.append({
                "code": code,
                "date": date_str,
                "open": int(row.get("시가", 0)),
                "high": int(row.get("고가", 0)),
                "low": int(row.get("저가", 0)),
                "close": close,
                "volume": int(row.get("거래량", 0)),
                "trade_value": None,
                "mktcap": None,
                "change_rate": float(row["등락률"]) if "등락률" in row and row["등락률"] else None,
            })

        if rows:
            db.insert_daily_prices(rows)
            total_rows += len(rows)

        if (i + 1) % 100 == 0:
            log(f"  {i+1}/{len(codes)} ({total_rows:,}건, {errors} errors)")

        time.sleep(0.3)  # KRX 부하 방지

    log(f"=== OHLCV 백필 완료: {total_rows:,}건 ({errors} errors) ===")
    return total_rows


def backfill_fundamentals(start_date: str, end_date: str):
    """종목별로 PER/PBR/EPS 수집 → daily_valuations 적재."""
    s = start_date.replace("-", "")
    e = end_date.replace("-", "")

    codes = db.get_all_codes()
    log(f"펀더멘탈 백필: {len(codes)}종목, {start_date} ~ {end_date}")
    total_rows = 0
    errors = 0

    for i, code in enumerate(codes):
        try:
            df = krx.get_market_fundamental_by_date(s, e, code)
        except Exception as ex:
            errors += 1
            time.sleep(1)
            continue

        if df.empty:
            continue

        rows = []
        for date_idx, row in df.iterrows():
            date_str = date_idx.strftime("%Y-%m-%d")
            per = row.get("PER", None)
            pbr = row.get("PBR", None)
            eps = row.get("EPS", None)
            bps = row.get("BPS", None)

            rows.append({
                "code": code,
                "date": date_str,
                "per": float(per) if per and per != 0 else None,
                "pbr": float(pbr) if pbr and pbr != 0 else None,
                "eps": float(eps) if eps and eps != 0 else None,
                "bps": float(bps) if bps and bps != 0 else None,
                "foreign_ratio": None,
            })

        if rows:
            db.upsert_daily_valuations(rows)
            total_rows += len(rows)

        if (i + 1) % 100 == 0:
            log(f"  펀더멘탈 {i+1}/{len(codes)} ({total_rows:,}건)")

        time.sleep(0.3)

    log(f"=== 펀더멘탈 백필 완료: {total_rows:,}건 ({errors} errors) ===")
    return total_rows


def main():
    parser = argparse.ArgumentParser(description="PyKRX OHLCV 백필")
    parser.add_argument("--start", help="시작일 (YYYY-MM-DD)")
    parser.add_argument("--end", default=datetime.now().strftime("%Y-%m-%d"), help="종료일")
    parser.add_argument("--months", type=int, default=60, help="최근 N개월 (start 미지정 시)")
    parser.add_argument("--skip-ohlcv", action="store_true", help="OHLCV 건너뛰기")
    parser.add_argument("--skip-fundamental", action="store_true", help="펀더멘탈 건너뛰기")
    args = parser.parse_args()

    if not args.start:
        start = (datetime.now() - timedelta(days=args.months * 30)).strftime("%Y-%m-%d")
    else:
        start = args.start

    log(f"백필 범위: {start} ~ {args.end}")

    if not args.skip_ohlcv:
        backfill_ohlcv(start, args.end)

    if not args.skip_fundamental:
        backfill_fundamentals(start, args.end)


if __name__ == "__main__":
    main()

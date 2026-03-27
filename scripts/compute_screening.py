#!/usr/bin/env python3
"""과거 날짜들에 대한 스크리닝 지표 일괄 계산.

사용법:
  python3 scripts/compute_screening.py                  # 오늘만
  python3 scripts/compute_screening.py --start 2026-03-01  # 3월 전체
"""

import argparse
import os
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "skills", "stock"))
sys.path.insert(0, os.path.join(ROOT, "skills", "stock", "screener_v2"))

os.environ.setdefault("KIS_THROTTLE", "0.5")
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))

import market_db as db


def log(msg):
    print(f"[screening {datetime.now():%H:%M:%S}] {msg}", flush=True)


def get_trading_dates(start, end):
    """daily_prices에서 거래일 목록 조회."""
    conn = db._get_conn()
    rows = conn.execute(
        "SELECT DISTINCT date FROM daily_prices WHERE date BETWEEN ? AND ? ORDER BY date",
        (start, end),
    ).fetchall()
    return [r["date"] for r in rows]


def compute_for_date(date_str):
    """특정 날짜의 스크리닝 지표 계산."""
    conn = db._get_conn()
    codes = db.get_active_codes()
    rows = []

    for code in codes:
        prices = conn.execute(
            "SELECT date, close, volume FROM daily_prices "
            "WHERE code=? AND date<=? ORDER BY date DESC LIMIT 120",
            (code, date_str),
        ).fetchall()

        if not prices or prices[0]["date"] != date_str:
            continue

        closes = [p["close"] for p in prices if p["close"]]
        volumes = [p["volume"] for p in prices if p["volume"]]

        if not closes:
            continue

        close = closes[0]

        def ma(n):
            return sum(closes[:n]) / n if len(closes) >= n else None

        def ret(n):
            return (closes[0] / closes[n] - 1) * 100 if len(closes) > n and closes[n] else None

        vol_avg_5 = sum(volumes[:5]) / 5 if len(volumes) >= 5 else None
        vol_ratio = volumes[0] / vol_avg_5 if vol_avg_5 and volumes else None

        val = conn.execute(
            "SELECT per, pbr, foreign_ratio FROM daily_valuations WHERE code=? AND date=?",
            (code, date_str),
        ).fetchone()

        price_row = conn.execute(
            "SELECT mktcap FROM daily_prices WHERE code=? AND date=?",
            (code, date_str),
        ).fetchone()

        flow_5 = conn.execute(
            "SELECT SUM(foreign_net) as f, SUM(institution_net) as i "
            "FROM (SELECT foreign_net, institution_net FROM investor_flow "
            "      WHERE code=? AND date<=? ORDER BY date DESC LIMIT 5)",
            (code, date_str),
        ).fetchone()

        flow_20 = conn.execute(
            "SELECT SUM(foreign_net) as f "
            "FROM (SELECT foreign_net FROM investor_flow "
            "      WHERE code=? AND date<=? ORDER BY date DESC LIMIT 20)",
            (code, date_str),
        ).fetchone()

        rows.append({
            "code": code,
            "date": date_str,
            "close": close,
            "mktcap": price_row["mktcap"] if price_row else None,
            "per": val["per"] if val else None,
            "pbr": val["pbr"] if val else None,
            "ma5": ma(5),
            "ma20": ma(20),
            "ma60": ma(60),
            "ma120": ma(120),
            "return_1d": ret(1),
            "return_5d": ret(5),
            "return_20d": ret(20),
            "return_60d": ret(60),
            "volume_ratio_5d": round(vol_ratio, 2) if vol_ratio else None,
            "foreign_net_5d": flow_5["f"] if flow_5 else None,
            "foreign_net_20d": flow_20["f"] if flow_20 else None,
            "institution_net_5d": flow_5["i"] if flow_5 else None,
            "foreign_ratio": val["foreign_ratio"] if val else None,
        })

    if rows:
        db.upsert_daily_screening(rows)
    return len(rows)


def main():
    parser = argparse.ArgumentParser(description="스크리닝 지표 계산")
    parser.add_argument("--start", help="시작일")
    parser.add_argument("--end", default=datetime.now().strftime("%Y-%m-%d"))
    args = parser.parse_args()

    db.init()
    start = args.start or args.end

    dates = get_trading_dates(start, args.end)
    log(f"{len(dates)}일 계산 대상: {start} ~ {args.end}")

    for i, date in enumerate(dates):
        n = compute_for_date(date)
        log(f"  {date}: {n}종목")


if __name__ == "__main__":
    main()

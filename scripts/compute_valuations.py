#!/usr/bin/env python3
"""EPS/BPS + 일별 종가 → daily_valuations PER/PBR 역산.

financials 테이블의 연간 EPS/BPS를 기반으로,
각 거래일의 종가에서 PER = 종가/EPS, PBR = 종가/BPS를 계산.

사용법:
  python3 scripts/compute_valuations.py                     # 전체 기간
  python3 scripts/compute_valuations.py --start 2024-01-01  # 특정 시작일
  python3 scripts/compute_valuations.py --limit 100         # 상위 100종목만
"""

import argparse
import os
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import market_db as db


def log(msg):
    print(f"[compute-val {datetime.now():%H:%M:%S}] {msg}", flush=True)


def get_eps_bps_timeline(code):
    """종목의 연간 EPS/BPS를 날짜 순서로 반환.

    Returns: [(effective_date, eps, bps), ...]
    effective_date = 결산 다음 해 시작일 (e.g., 2024 실적 → 2025-01-01부터 적용)
    """
    conn = db._get_conn()
    rows = conn.execute(
        """SELECT period, eps, bps FROM financials
           WHERE code=? AND period_type='annual' AND eps IS NOT NULL
           ORDER BY period ASC""",
        (code,),
    ).fetchall()

    timeline = []
    for r in rows:
        year = r["period"]
        if len(year) != 4:
            continue
        # 해당 연도 실적은 그 해 전체에 적용 (e.g., 2024 실적 → 2024-01-01~)
        effective_date = f"{year}-01-01"
        timeline.append((effective_date, r["eps"], r["bps"]))

    return timeline


def compute_valuations(start=None, end=None, limit=None):
    """전종목 PER/PBR 역산 → daily_valuations upsert."""
    db.init()
    conn = db._get_conn()

    codes = db.get_active_codes()
    if limit:
        codes = codes[:limit]

    log(f"밸류에이션 역산: {len(codes)}종목")
    total = 0
    skipped = 0

    for i, code in enumerate(codes):
        timeline = get_eps_bps_timeline(code)
        if not timeline:
            skipped += 1
            continue

        # 일별 종가 조회
        sql = "SELECT date, close FROM daily_prices WHERE code=?"
        params = [code]
        if start:
            sql += " AND date>=?"
            params.append(start)
        if end:
            sql += " AND date<=?"
            params.append(end)
        sql += " ORDER BY date ASC"

        prices = conn.execute(sql, params).fetchall()
        if not prices:
            continue

        # 타임라인 인덱스: 해당 날짜에 적용할 EPS/BPS 찾기
        rows = []
        ti = 0  # timeline index
        for p in prices:
            date = p["date"]
            close = p["close"]
            if not close or close <= 0:
                continue

            # 현재 날짜에 적용할 EPS/BPS 찾기 (가장 최근 것)
            while ti + 1 < len(timeline) and timeline[ti + 1][0] <= date:
                ti += 1

            if timeline[ti][0] > date:
                continue  # 아직 적용할 실적이 없음

            _, eps, bps = timeline[ti]

            per = round(close / eps, 2) if eps and eps > 0 else None
            pbr = round(close / bps, 2) if bps and bps > 0 else None

            rows.append({
                "code": code,
                "date": date,
                "per": per,
                "pbr": pbr,
                "eps": eps,
                "bps": bps,
                "foreign_ratio": None,  # 과거 데이터는 없음
            })

        if rows:
            db.upsert_daily_valuations(rows)
            total += len(rows)

        if (i + 1) % 200 == 0:
            log(f"  {i+1}/{len(codes)} ({total:,}건, {skipped} skipped)")

    log(f"=== 밸류에이션 역산 완료: {total:,}건 ({skipped} no financials) ===")
    return total


def main():
    parser = argparse.ArgumentParser(description="PER/PBR 역산")
    parser.add_argument("--start", help="시작일 (YYYY-MM-DD)")
    parser.add_argument("--end", help="종료일")
    parser.add_argument("--limit", type=int, help="상위 N종목만")
    args = parser.parse_args()

    compute_valuations(start=args.start, end=args.end, limit=args.limit)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""DART OpenAPI 재무제표 백필.

사전 조건:
  pip install opendartreader
  .env에 DART_API_KEY 추가 (https://opendart.fss.or.kr/ 에서 발급)

사용법:
  python3 scripts/backfill_financials.py              # 전종목 연간
  python3 scripts/backfill_financials.py --year 2024  # 특정 연도만
  python3 scripts/backfill_financials.py --limit 100  # 처음 100종목만
"""

import argparse
import os
import sys
import time
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))

import market_db as db

DART_API_KEY = os.environ.get("DART_API_KEY")


def log(msg):
    print(f"[dart {datetime.now():%H:%M:%S}] {msg}", flush=True)


def backfill_annual(years=None, limit=None):
    """전종목 연간 재무제표 수집 → financials 테이블."""
    if not DART_API_KEY:
        log("DART_API_KEY가 .env에 없습니다. https://opendart.fss.or.kr/ 에서 발급받으세요.")
        return 0

    try:
        import OpenDartReader
    except ImportError:
        log("opendartreader 설치 필요: pip install opendartreader")
        return 0

    dart = OpenDartReader(DART_API_KEY)
    db.init()

    if years is None:
        years = list(range(2019, datetime.now().year + 1))

    codes = db.get_all_codes()
    if limit:
        codes = codes[:limit]

    log(f"DART 재무제표 백필: {len(codes)}종목, {years}")
    total = 0
    errors = 0

    for i, code in enumerate(codes):
        rows = []
        for year in years:
            try:
                # 연간 손익계산서
                fs = dart.finstate(code, year, reprt_code="11011")  # 11011=사업보고서(연간)
                if fs is None or fs.empty:
                    continue

                revenue = _extract_amount(fs, "매출액")
                oper_profit = _extract_amount(fs, "영업이익")
                net_profit = _extract_amount(fs, "당기순이익")

                if revenue is None and oper_profit is None and net_profit is None:
                    continue

                rows.append({
                    "code": code,
                    "period": str(year),
                    "period_type": "annual",
                    "revenue": revenue,
                    "oper_profit": oper_profit,
                    "net_profit": net_profit,
                    "roe": None,
                })

            except Exception:
                errors += 1
                continue

            time.sleep(0.15)  # DART 일 10,000건 제한 고려

        if rows:
            db.upsert_financials(rows)
            total += len(rows)

        if (i + 1) % 50 == 0:
            log(f"  {i+1}/{len(codes)} ({total}건, {errors} errors)")

    log(f"=== DART 백필 완료: {total}건 ({errors} errors) ===")
    return total


def _extract_amount(fs, account_name):
    """재무제표에서 특정 계정 금액 추출 (억원 변환)."""
    # 연결재무제표 우선, 없으면 별도재무제표
    for fs_div in ["CFS", "OFS"]:
        row = fs[(fs["account_nm"].str.contains(account_name, na=False)) &
                 (fs["fs_div"] == fs_div)]
        if not row.empty:
            val = row.iloc[0].get("thstrm_amount", "")
            if val and val != "":
                try:
                    # 원 단위 → 억원
                    return int(float(str(val).replace(",", ""))) // 100_000_000
                except (ValueError, TypeError):
                    pass
    return None


def main():
    parser = argparse.ArgumentParser(description="DART 재무제표 백필")
    parser.add_argument("--year", type=int, help="특정 연도만")
    parser.add_argument("--limit", type=int, help="종목 수 제한")
    args = parser.parse_args()

    years = [args.year] if args.year else None
    backfill_annual(years=years, limit=args.limit)


if __name__ == "__main__":
    main()

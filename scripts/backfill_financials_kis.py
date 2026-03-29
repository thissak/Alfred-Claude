#!/usr/bin/env python3
"""KIS API 재무제표 백필 — 손익계산서 + 재무비율(EPS/BPS/ROE).

사용법:
  python3 scripts/backfill_financials_kis.py              # 전종목 연간+분기
  python3 scripts/backfill_financials_kis.py --annual-only # 연간만
  python3 scripts/backfill_financials_kis.py --limit 100   # 상위 100종목만
"""

import argparse
import os
import sys
import time
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

os.environ.setdefault("KIS_THROTTLE", "0.067")

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))

import market_db as db
from kis_readonly_client import get as kis_get


def log(msg):
    print(f"[backfill-fin {datetime.now():%H:%M:%S}] {msg}", flush=True)


def _safe_float(v):
    try:
        f = float(v)
        return f if f != 0 and f != 99.99 else None
    except (TypeError, ValueError):
        return None


def _safe_int(v):
    try:
        i = int(float(v))
        return i if i != 0 else None
    except (TypeError, ValueError):
        return None


def _stac_yymm_to_period(stac_yymm, div_cls):
    """결산년월 → period 문자열 변환.

    연간: '202412' → '2024'
    분기: '202503' → '2025Q1', '202506' → '2025Q2', ...
    """
    if not stac_yymm or len(stac_yymm) < 6:
        return None
    year = stac_yymm[:4]
    month = int(stac_yymm[4:6])

    if div_cls == "0":  # 연간
        return year

    # 분기: 3→Q1, 6→Q2, 9→Q3, 12→Q4
    quarter_map = {3: "Q1", 6: "Q2", 9: "Q3", 12: "Q4"}
    q = quarter_map.get(month)
    if not q:
        # 비표준 결산월 — 가장 가까운 분기 매핑
        q = f"Q{(month - 1) // 3 + 1}" if month > 0 else "Q4"
    return f"{year}{q}"


def fetch_financials(code, div_cls="0"):
    """손익계산서 + 재무비율 → financials 행 리스트.

    div_cls: '0'=연간, '1'=분기
    """
    period_type = "annual" if div_cls == "0" else "quarterly"

    # 1) 손익계산서
    income = {}
    data = kis_get(
        "/uapi/domestic-stock/v1/finance/income-statement",
        "FHKST66430200",
        {"FID_DIV_CLS_CODE": div_cls, "fid_cond_mrkt_div_code": "J",
         "fid_input_iscd": code},
    )
    if data and data.get("output"):
        for item in data["output"]:
            yymm = item.get("stac_yymm", "")
            period = _stac_yymm_to_period(yymm, div_cls)
            if not period:
                continue
            income[period] = {
                "revenue": _safe_int(item.get("sale_account")),
                "oper_profit": _safe_int(item.get("bsop_prti")),
                "net_profit": _safe_int(item.get("thtr_ntin")),
            }

    # 2) 재무비율 (EPS/BPS/ROE)
    ratios = {}
    data2 = kis_get(
        "/uapi/domestic-stock/v1/finance/financial-ratio",
        "FHKST66430300",
        {"FID_DIV_CLS_CODE": div_cls, "fid_cond_mrkt_div_code": "J",
         "fid_input_iscd": code},
    )
    if data2 and data2.get("output"):
        for item in data2["output"]:
            yymm = item.get("stac_yymm", "")
            period = _stac_yymm_to_period(yymm, div_cls)
            if not period:
                continue
            ratios[period] = {
                "eps": _safe_float(item.get("eps")),
                "bps": _safe_float(item.get("bps")),
                "roe": _safe_float(item.get("roe_val")),
            }

    # 병합
    all_periods = set(list(income.keys()) + list(ratios.keys()))
    rows = []
    for period in sorted(all_periods):
        inc = income.get(period, {})
        rat = ratios.get(period, {})
        rows.append({
            "code": code,
            "period": period,
            "period_type": period_type,
            "revenue": inc.get("revenue"),
            "oper_profit": inc.get("oper_profit"),
            "net_profit": inc.get("net_profit"),
            "roe": rat.get("roe"),
            "eps": rat.get("eps"),
            "bps": rat.get("bps"),
        })

    return rows


def backfill(annual_only=False, limit=None):
    """전종목 재무제표 백필."""
    db.init()

    codes = db.get_active_codes()
    if limit:
        codes = codes[:limit]

    log(f"재무제표 백필: {len(codes)}종목 (annual_only={annual_only})")
    total = 0
    errors = 0

    for i, code in enumerate(codes):
        try:
            # 연간
            rows = fetch_financials(code, "0")
            if rows:
                db.upsert_financials(rows)
                total += len(rows)

            # 분기
            if not annual_only:
                rows_q = fetch_financials(code, "1")
                if rows_q:
                    db.upsert_financials(rows_q)
                    total += len(rows_q)

        except Exception as e:
            errors += 1
            if errors % 50 == 0:
                log(f"  에러 누적 {errors}건: {e}")

        if (i + 1) % 100 == 0:
            log(f"  {i+1}/{len(codes)} ({total:,}건, {errors} errors)")

    log(f"=== 재무제표 백필 완료: {total:,}건 ({errors} errors) ===")
    return total


def main():
    parser = argparse.ArgumentParser(description="KIS 재무제표 백필")
    parser.add_argument("--annual-only", action="store_true", help="연간만")
    parser.add_argument("--limit", type=int, help="상위 N종목만")
    args = parser.parse_args()

    backfill(annual_only=args.annual_only, limit=args.limit)


if __name__ == "__main__":
    main()

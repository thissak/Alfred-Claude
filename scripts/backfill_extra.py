#!/usr/bin/env python3
"""추가 재무 데이터 + 공매도 백필.

1) 대차대조표, 안정성비율, 성장성비율, 기타주요비율 → financials 테이블 확장
2) 공매도 일별추이 → daily_short_selling 테이블

사용법:
  python3 scripts/backfill_extra.py                    # 전체
  python3 scripts/backfill_extra.py --limit 100        # 상위 100종목
  python3 scripts/backfill_extra.py --only financials   # 재무만
  python3 scripts/backfill_extra.py --only short        # 공매도만
"""

import argparse
import os
import sys
import time
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

os.environ.setdefault("KIS_THROTTLE", "0.067")

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))

import market_db as db
from kis_readonly_client import get as kis_get


def log(msg):
    print(f"[backfill-extra {datetime.now():%H:%M:%S}] {msg}", flush=True)


def _sf(v):
    """Safe float."""
    try:
        f = float(v)
        return f if f != 0 else None
    except (TypeError, ValueError):
        return None


def _si(v):
    """Safe int."""
    try:
        i = int(float(v))
        return i if i != 0 else None
    except (TypeError, ValueError):
        return None


def _stac_to_period(stac_yymm, div_cls):
    if not stac_yymm or len(stac_yymm) < 6:
        return None
    year = stac_yymm[:4]
    month = int(stac_yymm[4:6])
    if div_cls == "0":
        return year
    quarter_map = {3: "Q1", 6: "Q2", 9: "Q3", 12: "Q4"}
    q = quarter_map.get(month, f"Q{(month - 1) // 3 + 1}" if month > 0 else "Q4")
    return f"{year}{q}"


# ── 추가 재무 백필 ──────────────────────────────────────


def fetch_extra_financials(code, div_cls="0"):
    """대차대조표 + 안정성 + 성장성 + 기타비율 → rows."""
    period_type = "annual" if div_cls == "0" else "quarterly"
    merged = {}  # period → dict

    # 대차대조표
    data = kis_get(
        "/uapi/domestic-stock/v1/finance/balance-sheet", "FHKST66430100",
        {"FID_DIV_CLS_CODE": div_cls, "fid_cond_mrkt_div_code": "J",
         "fid_input_iscd": code},
    )
    if data and data.get("output"):
        for item in data["output"]:
            p = _stac_to_period(item.get("stac_yymm", ""), div_cls)
            if not p:
                continue
            merged.setdefault(p, {}).update({
                "total_asset": _si(item.get("total_aset")),
                "total_liability": _si(item.get("total_lblt")),
                "total_equity": _si(item.get("total_cptl")),
            })

    # 안정성비율
    data = kis_get(
        "/uapi/domestic-stock/v1/finance/stability-ratio", "FHKST66430600",
        {"FID_DIV_CLS_CODE": div_cls, "fid_cond_mrkt_div_code": "J",
         "fid_input_iscd": code},
    )
    if data and data.get("output"):
        for item in data["output"]:
            p = _stac_to_period(item.get("stac_yymm", ""), div_cls)
            if not p:
                continue
            merged.setdefault(p, {}).update({
                "debt_ratio": _sf(item.get("lblt_rate")),
                "current_ratio": _sf(item.get("crnt_rate")),
            })

    # 성장성비율
    data = kis_get(
        "/uapi/domestic-stock/v1/finance/growth-ratio", "FHKST66430800",
        {"FID_DIV_CLS_CODE": div_cls, "fid_cond_mrkt_div_code": "J",
         "fid_input_iscd": code},
    )
    if data and data.get("output"):
        for item in data["output"]:
            p = _stac_to_period(item.get("stac_yymm", ""), div_cls)
            if not p:
                continue
            merged.setdefault(p, {}).update({
                "revenue_growth": _sf(item.get("grs")),
                "oper_profit_growth": _sf(item.get("bsop_prfi_inrt")),
            })

    # 기타주요비율
    data = kis_get(
        "/uapi/domestic-stock/v1/finance/other-major-ratios", "FHKST66430500",
        {"FID_DIV_CLS_CODE": div_cls, "fid_cond_mrkt_div_code": "J",
         "fid_input_iscd": code},
    )
    if data and data.get("output"):
        for item in data["output"]:
            p = _stac_to_period(item.get("stac_yymm", ""), div_cls)
            if not p:
                continue
            merged.setdefault(p, {}).update({
                "ebitda": _si(item.get("ebitda")),
                "ev_ebitda": _sf(item.get("ev_ebitda")),
                "payout_rate": _sf(item.get("payout_rate")),
            })

    # 행 구성 — 기존 데이터에 병합되도록 나머지 필드는 None
    rows = []
    for period, vals in sorted(merged.items()):
        row = {
            "code": code,
            "period": period,
            "period_type": period_type,
            "revenue": None, "oper_profit": None, "net_profit": None,
            "roe": None, "eps": None, "bps": None,
        }
        row.update(vals)
        rows.append(row)

    return rows


def backfill_extra_financials(limit=None):
    """전종목 추가 재무 백필."""
    db.init()
    codes = db.get_active_codes()
    if limit:
        codes = codes[:limit]

    log(f"추가 재무 백필: {len(codes)}종목 (대차대조표/안정성/성장성/기타)")
    total = 0
    errors = 0

    for i, code in enumerate(codes):
        try:
            for div_cls in ["0", "1"]:  # 연간 + 분기
                rows = fetch_extra_financials(code, div_cls)
                if rows:
                    db.upsert_financials(rows)
                    total += len(rows)
        except Exception as e:
            errors += 1
            if errors % 50 == 0:
                log(f"  에러 누적 {errors}건: {e}")

        if (i + 1) % 100 == 0:
            log(f"  재무 {i+1}/{len(codes)} ({total:,}건, {errors} errors)")

    log(f"=== 추가 재무 완료: {total:,}건 ({errors} errors) ===")
    return total


# ── 공매도 백필 ─────────────────────────────────────────


def fetch_short_selling(code, start, end):
    """공매도 일별추이 조회."""
    data = kis_get(
        "/uapi/domestic-stock/v1/quotations/daily-short-sale", "FHPST04830000",
        {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code,
         "FID_INPUT_DATE_1": start.replace("-", ""),
         "FID_INPUT_DATE_2": end.replace("-", "")},
    )
    if not data:
        return []

    out = data.get("output2", [])
    rows = []
    for item in out:
        date_raw = item.get("stck_bsop_date", "")
        if len(date_raw) != 8:
            continue
        date_str = f"{date_raw[:4]}-{date_raw[4:6]}-{date_raw[6:8]}"
        rows.append({
            "code": code,
            "date": date_str,
            "short_volume": _si(item.get("ssts_cntg_qty")),
            "short_value": _si(item.get("ssts_tr_pbmn")),
            "short_ratio": _sf(item.get("ssts_vol_rlim")),
        })

    return rows


def backfill_short_selling(limit=None):
    """전종목 공매도 백필 — 최근 3개월씩 청크."""
    db.init()
    codes = db.get_active_codes()
    if limit:
        codes = codes[:limit]

    # 날짜 범위: 최근 1년 (API 한번에 최대 ~3개월분 반환)
    end = datetime.now()
    chunks = []
    for m in range(0, 12, 3):
        c_end = end - timedelta(days=m * 30)
        c_start = c_end - timedelta(days=90)
        chunks.append((c_start.strftime("%Y-%m-%d"), c_end.strftime("%Y-%m-%d")))

    log(f"공매도 백필: {len(codes)}종목 × {len(chunks)}청크")
    total = 0
    errors = 0

    for i, code in enumerate(codes):
        for start, end_str in chunks:
            try:
                rows = fetch_short_selling(code, start, end_str)
                if rows:
                    db.upsert_daily_short_selling(rows)
                    total += len(rows)
            except Exception as e:
                errors += 1

        if (i + 1) % 100 == 0:
            log(f"  공매도 {i+1}/{len(codes)} ({total:,}건, {errors} errors)")

    log(f"=== 공매도 백필 완료: {total:,}건 ({errors} errors) ===")
    return total


# ── Main ────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="추가 데이터 백필")
    parser.add_argument("--limit", type=int, help="상위 N종목만")
    parser.add_argument("--only", choices=["financials", "short"], help="특정 카테고리만")
    args = parser.parse_args()

    if not args.only or args.only == "financials":
        backfill_extra_financials(limit=args.limit)

    if not args.only or args.only == "short":
        backfill_short_selling(limit=args.limit)


if __name__ == "__main__":
    main()

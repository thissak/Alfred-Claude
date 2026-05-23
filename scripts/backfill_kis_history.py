#!/usr/bin/env python3
"""KIS 일봉 과거 백필 — daily_prices를 상장일(최대 ~1996)까지 확장.

FHKST03010100 (inquire-daily-itemchartprice), 수정주가("0"), 100행/콜 페이지네이션.
종목별 현재 MIN(date) 이전 구간을 채운다. 멱등(upsert) + 체크포인트 재개.

맥미니에서 실행 (로컬 market.db 직접 쓰기 + KIS 토큰). 쓰로틀은 KIS_THROTTLE 환경변수.

사용법:
  KIS_THROTTLE=0.1 python3 scripts/backfill_kis_history.py --pilot
  KIS_THROTTLE=0.1 python3 scripts/backfill_kis_history.py
  python3 scripts/backfill_kis_history.py --floor 20100101
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import market_db as db
import kis_readonly_client as kis

PATH = "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
TR = "FHKST03010100"
CKPT = os.path.join(ROOT, "run", "backfill_kis_done.json")
DEFAULT_FLOOR = "19900101"
PILOT = ["005930", "000660", "263750", "471990", "0080G0"]  # 삼성·하이닉스·펄어비스·ETF2


def log(m):
    print(f"[backfill {datetime.now():%H:%M:%S}] {m}", flush=True)


def _load_ckpt():
    try:
        return set(json.load(open(CKPT)))
    except Exception:
        return set()


def _save_ckpt(done):
    os.makedirs(os.path.dirname(CKPT), exist_ok=True)
    json.dump(sorted(done), open(CKPT, "w"))


def _fetch(code, date_2, floor):
    """일봉 1콜 (최신 100건 ≤ date_2). None=에러(레이트/장애), []=상장일 도달."""
    p = {
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_INPUT_ISCD": code,
        "FID_INPUT_DATE_1": floor,
        "FID_INPUT_DATE_2": date_2,
        "FID_PERIOD_DIV_CODE": "D",
        "FID_ORG_ADJ_PRC": "0",  # 수정주가 (분할 연속성)
    }
    for attempt in range(3):
        try:
            data = kis.get(PATH, TR, p)  # rt_cd≠0 이면 None
        except Exception as e:
            data = None
            if attempt == 2:
                log(f"  {code} @ {date_2} 예외: {e}")
        if data is not None:
            return data.get("output2") or []
        time.sleep(2 ** attempt)  # 1s, 2s, 4s 백오프
    return None  # 3회 실패 → 에러


def _rows(code, o2):
    out = []
    for r in o2:
        ds = r.get("stck_bsop_date")
        clpr = r.get("stck_clpr")
        if not ds or not clpr or int(clpr) == 0:
            continue
        out.append({
            "code": code,
            "date": f"{ds[:4]}-{ds[4:6]}-{ds[6:8]}",
            "open": int(r.get("stck_oprc") or 0),
            "high": int(r.get("stck_hgpr") or 0),
            "low": int(r.get("stck_lwpr") or 0),
            "close": int(clpr),
            "volume": int(r.get("acml_vol") or 0),
            "trade_value": int(r.get("acml_tr_pbmn") or 0),
            "mktcap": None,
            "change_rate": None,  # 과거행은 NULL (차트가 자체 계산)
        })
    return out


def backfill_code(code, floor):
    """종목 1개 백필. (추가행수, ok) — ok=False면 에러로 미완료."""
    cur = db._query("SELECT MIN(date) m FROM daily_prices WHERE code=?", [code])
    min_date = cur[0]["m"] if cur else None
    end = (datetime.strptime(min_date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y%m%d") \
        if min_date else datetime.now().strftime("%Y%m%d")

    added = 0
    while end >= floor:
        o2 = _fetch(code, end, floor)
        if o2 is None:
            return added, False        # 에러 → 체크포인트 미기록
        if not o2:
            break                      # 상장일 도달
        rows = _rows(code, o2)
        if not rows:
            break
        db.upsert_daily_prices(rows)
        added += len(rows)
        earliest = min(r["date"] for r in rows)
        if earliest.replace("-", "") >= end:  # 진전 없음 안전장치
            break
        end = (datetime.strptime(earliest, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y%m%d")
    return added, True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", action="store_true", help="파일럿 5종목만")
    ap.add_argument("--floor", default=DEFAULT_FLOOR, help="하한 YYYYMMDD")
    args = ap.parse_args()

    db.init()
    if args.pilot:
        codes, done = PILOT, set()
    else:
        codes = [r["code"] for r in db._query("SELECT DISTINCT code FROM daily_prices ORDER BY code")]
        done = _load_ckpt()

    remaining = [c for c in codes if c not in done]
    log(f"시작: {len(remaining)}/{len(codes)}종목, floor={args.floor}, "
        f"throttle={os.environ.get('KIS_THROTTLE', '0.5')}")

    total = errors = 0
    for i, code in enumerate(codes):
        if code in done:
            continue
        added, ok = backfill_code(code, args.floor)
        total += added
        if ok and not args.pilot:
            done.add(code)
            if len(done) % 50 == 0:
                _save_ckpt(done)
        if not ok:
            errors += 1
        if args.pilot or (i + 1) % 50 == 0:
            mn = db._query("SELECT MIN(date) m FROM daily_prices WHERE code=?", [code])[0]["m"]
            log(f"  [{i+1}/{len(codes)}] {code} +{added}행 (MIN={mn}) 누적 {total:,}행 {errors}err")

    if not args.pilot:
        _save_ckpt(done)
    log(f"=== 완료: +{total:,}행, {errors}에러, 완료 {len(done)}종목 ===")


if __name__ == "__main__":
    main()

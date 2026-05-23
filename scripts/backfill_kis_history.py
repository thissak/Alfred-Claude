#!/usr/bin/env python3
"""KIS 일봉 과거 백필 (병렬) — daily_prices를 상장일/최대 1996까지 확장.

FHKST03010100 수정주가("0"), 100행/콜. 스레드풀 + 전역 레이트게이트로 동시 요청.
KIS 콜 지연(~4.6초)은 latency라 병렬로 겹쳐 처리. 한계는 "초당 거래건수"(~13 RPS)이므로
RATE(기본 10/s)로 게이트하고 초과 시 재시도. 종목별 MIN(date) 이전을 채운다.
멱등(upsert) + 체크포인트 재개. 맥미니에서 실행 (로컬 market.db + KIS 토큰).

사용법:
  python3 scripts/backfill_kis_history.py --pilot
  RATE=10 WORKERS=45 python3 scripts/backfill_kis_history.py
"""
import argparse
import concurrent.futures as cf
import json
import os
import sqlite3
import sys
import threading
import time
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
os.environ.setdefault("KIS_THROTTLE", "0")  # 레이트는 아래 gate가 통제 (클라 내부 sleep off)
import market_db as db
import kis_readonly_client as kis

PATH = "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
TR = "FHKST03010100"
DB_PATH = os.path.join(ROOT, "data", "market.db")
CKPT = os.path.join(ROOT, "run", "backfill_kis_done.json")
DEFAULT_FLOOR = "19900101"
PILOT = ["000150", "000180", "000210", "000220", "000240"]  # 미백필 구형 종목 (병렬 다중페이지 검증)
RATE = float(os.environ.get("RATE", "10"))       # 초당 콜 상한
WORKERS = int(os.environ.get("WORKERS", "45"))


def log(m):
    print(f"[backfill {datetime.now():%H:%M:%S}] {m}", flush=True)


# ── 전역 레이트게이트 (초당 RATE) ──
_rl_lock = threading.Lock()
_next_slot = [0.0]


def gate():
    with _rl_lock:
        now = time.time()
        wait = _next_slot[0] - now
        _next_slot[0] = max(now, _next_slot[0]) + 1.0 / RATE
    if wait > 0:
        time.sleep(wait)


# ── 스레드 공유 쓰기 커넥션 (락 보호, WAL) ──
_wconn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=60)
_wconn.execute("PRAGMA journal_mode=WAL")
_wconn.execute("PRAGMA busy_timeout=60000")
_wlock = threading.Lock()

_UPSERT = """INSERT INTO daily_prices
    (code,date,open,high,low,close,volume,trade_value,mktcap,change_rate)
    VALUES (:code,:date,:open,:high,:low,:close,:volume,:trade_value,:mktcap,:change_rate)
    ON CONFLICT(code,date) DO UPDATE SET
        open=excluded.open, high=excluded.high, low=excluded.low,
        close=excluded.close, volume=excluded.volume, trade_value=excluded.trade_value"""


def upsert(rows):
    with _wlock:
        _wconn.executemany(_UPSERT, rows)
        _wconn.commit()


# ── 체크포인트 (락 보호) ──
_ck_lock = threading.Lock()


def mark_done(done, code):
    with _ck_lock:
        done.add(code)
        if len(done) % 50 == 0:
            json.dump(sorted(done), open(CKPT, "w"))


def fetch(code, end, floor):
    """1콜 (최신 100건 ≤ end). None=재시도 소진(에러), []=상장일 도달."""
    p = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code,
         "FID_INPUT_DATE_1": floor, "FID_INPUT_DATE_2": end,
         "FID_PERIOD_DIV_CODE": "D", "FID_ORG_ADJ_PRC": "0"}
    for _ in range(6):
        gate()
        try:
            d = kis.get(PATH, TR, p)  # rt_cd≠0(초당초과 등) → None
        except Exception:
            d = None
        if d is not None:
            return d.get("output2") or []
        time.sleep(0.4)  # 레이트리밋 완화 후 재시도
    return None


def rows_of(code, o2):
    out = []
    for r in o2:
        ds, clpr = r.get("stck_bsop_date"), r.get("stck_clpr")
        if not ds or not clpr or int(clpr) == 0:
            continue
        out.append({
            "code": code, "date": f"{ds[:4]}-{ds[4:6]}-{ds[6:8]}",
            "open": int(r.get("stck_oprc") or 0), "high": int(r.get("stck_hgpr") or 0),
            "low": int(r.get("stck_lwpr") or 0), "close": int(clpr),
            "volume": int(r.get("acml_vol") or 0), "trade_value": int(r.get("acml_tr_pbmn") or 0),
            "mktcap": None, "change_rate": None,
        })
    return out


def backfill_code(code, min_date, floor):
    """(추가행수, ok). ok=False면 에러로 미완료."""
    end = (datetime.strptime(min_date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y%m%d") \
        if min_date else datetime.now().strftime("%Y%m%d")
    added = 0
    while end >= floor:
        o2 = fetch(code, end, floor)
        if o2 is None:
            return added, False
        if not o2:
            break
        rows = rows_of(code, o2)
        if not rows:
            break
        upsert(rows)
        added += len(rows)
        earliest = min(r["date"] for r in rows)
        if earliest.replace("-", "") >= end:
            break
        end = (datetime.strptime(earliest, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y%m%d")
    return added, True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", action="store_true")
    ap.add_argument("--floor", default=DEFAULT_FLOOR)
    args = ap.parse_args()

    mins = {r["code"]: r["m"] for r in
            db._query("SELECT code, MIN(date) m FROM daily_prices GROUP BY code")}
    if args.pilot:
        codes, done = PILOT, set()
    else:
        codes = sorted(mins.keys())
        try:
            done = set(json.load(open(CKPT)))
        except Exception:
            done = set()
    todo = [c for c in codes if c not in done]
    log(f"시작(병렬): {len(todo)}/{len(codes)}종목, RATE={RATE}/s, WORKERS={WORKERS}, floor={args.floor}")

    total = [0]
    errors = [0]
    n = [0]
    tlock = threading.Lock()

    def work(code):
        added, ok = backfill_code(code, mins.get(code), args.floor)
        with tlock:
            total[0] += added
            n[0] += 1
            if not ok:
                errors[0] += 1
            cur = n[0]
        if ok and not args.pilot:
            mark_done(done, code)
        if args.pilot:
            log(f"  {code} +{added}행 (ok={ok})")
        elif cur % 100 == 0:
            log(f"  {cur}/{len(todo)} 완료, 누적 +{total[0]:,}행, {errors[0]}에러")

    with cf.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        list(ex.map(work, todo))

    if not args.pilot:
        json.dump(sorted(done), open(CKPT, "w"))
    log(f"=== 완료: +{total[0]:,}행, {errors[0]}에러, 완료 {len(done)}종목 ===")


if __name__ == "__main__":
    main()

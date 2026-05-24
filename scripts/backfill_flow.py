#!/usr/bin/env python3
"""investor_flow + valuations + screening 백필 — freshness 보조테이블 복구.

daily_prices(PyKRX 경로)는 최신인데 KIS 기반 수급/밸류/스크리닝이 뒤처졌을 때 사용.
collector_daemon의 함수를 그대로 재사용한다(멱등 upsert). 맥미니에서 실행
(로컬 market.db 쓰기 필요 — MARKET_DB_HOST 설정 시 HTTP는 읽기전용이라 쓰기 불가).

사용법:
  python3 scripts/backfill_flow.py                 # 자동: 보조테이블 최신+1 ~ 거래일 최신
  python3 scripts/backfill_flow.py --since 2026-05-21
"""
import argparse
import os
import subprocess
import sys
import time
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)  # `import daemons.collector_daemon`


def log(msg):
    print(f"[backfill-flow {datetime.now():%H:%M:%S}] {msg}", flush=True)


def main():
    ap = argparse.ArgumentParser(description="수급/밸류/스크리닝 백필")
    ap.add_argument("--since", help="복구 시작일 YYYY-MM-DD (미지정 시 자동 탐지)")
    args = ap.parse_args()

    # collector_daemon import 시 src/skills 경로 + .env + KIS throttle 세팅됨
    import daemons.collector_daemon as c
    db = c.db
    db.init()
    t0 = time.time()

    latest_trade = db._query("SELECT MAX(date) d FROM daily_prices")[0]["d"]
    flow_latest = db._query("SELECT MAX(date) d FROM investor_flow")[0]["d"]
    scr_latest = db._query("SELECT MAX(date) d FROM daily_screening")[0]["d"]
    val_latest = db._query("SELECT MAX(date) d FROM daily_valuations")[0]["d"]

    # 스크리닝 누락 거래일 = daily_prices엔 있고 daily_screening엔 없는 날
    miss_days = [r["date"] for r in db._query(
        "SELECT DISTINCT date FROM daily_prices "
        "WHERE date > ? AND date NOT IN (SELECT date FROM daily_screening) "
        "ORDER BY date", (args.since or scr_latest or "1900-01-01",))]

    secondary_stale = (
        (flow_latest or "") < latest_trade
        or (scr_latest or "") < latest_trade
        or bool(miss_days)
    )
    log(f"거래일 {latest_trade} | flow {flow_latest} | val {val_latest} | "
        f"screening {scr_latest} | 누락스크리닝 {len(miss_days)}일")

    if not args.since and not secondary_stale:
        log("모든 보조테이블 최신 — skip")
        return

    since = args.since or min(x for x in (flow_latest, scr_latest, val_latest) if x)

    # 1) 전종목 수급 30일 재수집 (누락일 포함, 멱등)
    n = c.scan_investor_flow()
    log(f"investor_flow upsert={n}")

    # 2) 밸류에이션 per/pbr 보강
    subprocess.run(
        [sys.executable, os.path.join(ROOT, "scripts", "compute_valuations.py"),
         "--start", since],
        cwd=ROOT, check=False,
    )
    log("valuations done")

    # 3) 스크리닝 재계산 (누락 거래일마다) — 위 단계 반영 위해 재조회
    miss_days = [r["date"] for r in db._query(
        "SELECT DISTINCT date FROM daily_prices "
        "WHERE date >= ? AND date NOT IN (SELECT date FROM daily_screening) "
        "ORDER BY date", (since,))]
    for d in miss_days:
        c.compute_screening(d)
        log(f"screening {d} done")

    log(f"DONE in {time.time()-t0:.0f}s ({len(miss_days)} screening days)")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""freshness_monitor.py — daily_prices 데이터 신선도/완전성 독립 검사기.

collector의 자기보고(heartbeat)와 무관하게 DB를 직접 읽어
"와야 할 데이터가 실제 왔는가"를 검증한다 (liveness가 아니라 freshness).

검사:
  1. 완전성: 거래일(daily_indices=오라클) 각각의 daily_prices 행수가
     최근 정상일 중앙값의 90% 이상인가. 미만이면 부분수집(gap).
  2. 신선도: daily_prices 최신일이 daily_indices 최신일보다 뒤처지면 stale.
  3. 보조테이블: investor_flow/daily_screening 최신일이 거래일 최신보다 뒤처지면
     stale (KIS 경로가 PyKRX OHLCV와 별개로 정체되는 사각지대).

동작:
  - gap/stale 발견 → iMessage 알림(상태변화 시 1회) + 자동복구(backfill --since).
  - 정상 → heartbeat ok.

한계: daily_indices에 없는 날(=collector 전량실패로 지수도 못 받은 날)은
      외부 거래일 캘린더가 없어 interior 누락은 못 잡는다. stale 검사로 최신일
      정체는 잡힌다. ETF/특수코드 과거갭은 일봉차트 API가 미커버.

환경변수:
  FRESHNESS_INTERVAL=1800
  FRESHNESS_AUTOHEAL=1     (0이면 알림만, 자동 백필 안 함)
  FRESHNESS_LOOKBACK=10    (검사할 최근 거래일 수)
"""
import json
import os
import subprocess
import sys
from datetime import datetime
from statistics import median

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from monitor_base import MonitorBase
import market_db as db

STATUS_PATH = os.path.join(ROOT, "run", "freshness_status.json")


class FreshnessMonitor(MonitorBase):
    name = "freshness"
    interval = 1800

    def on_start(self):
        db.init()

    def check(self):
        lookback = int(os.environ.get("FRESHNESS_LOOKBACK", "10"))

        # 거래일 후보 = 최근 daily_prices 날짜 ∪ daily_indices 날짜.
        # 둘 중 하나라도 있으면 거래일로 본다 — 부분수집일은 prices에 적은 행으로,
        # 지수만 들어온 날은 indices에 잡혀서, collector가 어느 쪽을 놓쳐도 감지된다.
        price_dates = [r["date"] for r in db._query(
            "SELECT DISTINCT date FROM daily_prices ORDER BY date DESC LIMIT ?", (lookback,))]
        idx_dates = [r["date"] for r in db._query(
            "SELECT DISTINCT date FROM daily_indices WHERE code='0001' "
            "ORDER BY date DESC LIMIT ?", (lookback,))]
        if not price_dates and not idx_dates:
            return ("error", "daily_prices/indices 비어있음")
        cand = sorted(set(price_dates) | set(idx_dates), reverse=True)[:lookback]

        # 날짜별 daily_prices 행수
        counts = {r["date"]: r["n"] for r in db._query(
            "SELECT date, COUNT(*) n FROM daily_prices WHERE date>=? GROUP BY date",
            (cand[-1],))}

        # 완전성 기준 = 후보일 행수 중앙값 × 0.9
        vals = [counts.get(d, 0) for d in cand]
        med = median([v for v in vals if v]) if any(vals) else 0
        gaps = [(d, counts.get(d, 0)) for d in cand
                if med and counts.get(d, 0) < med * 0.9]

        # 신선도: prices 최신일이 거래일 최신보다 뒤처짐 (지수만 들어온 경우 등)
        latest_price = price_dates[0] if price_dates else None
        latest_trade = cand[0]
        stale = bool(latest_price) and latest_price < latest_trade

        # 보조테이블 신선도 — KIS 경로(수급/스크리닝)는 daily_prices(PyKRX)와 별개라
        # 따로 정체될 수 있다(daily_prices만 보면 못 잡는 사각지대).
        sec_stale = {}
        for t in ("investor_flow", "daily_screening"):
            d = db._query(f"SELECT MAX(date) d FROM {t}")[0]["d"] or ""
            if d and d < latest_trade:
                sec_stale[t] = d

        if not gaps and not stale and not sec_stale:
            self._transition("ok", f"정상 (최신 {latest_price}, 중앙값 {int(med)}행)")
            return f"정상 (최신 {latest_price}, 중앙값 {int(med)}행)"

        parts = []
        if stale:
            parts.append(f"stale(prices {latest_price} < 거래일 {latest_trade})")
        if gaps:
            g = ", ".join(f"{d}:{n}" for d, n in gaps[:5])
            parts.append(f"부분수집 {len(gaps)}일 [{g}] (정상 {int(med)})")
        if sec_stale:
            s = ", ".join(f"{t} {d}" for t, d in sec_stale.items())
            parts.append(f"보조테이블 정체 [{s}] < 거래일 {latest_trade}")
        detail = "; ".join(parts)

        first_bad = self._transition("bad", detail)
        if first_bad:
            self.write_outbox(f"⚠️ 데이터 신선도 경보\n{detail}")
            if gaps or stale:
                self._heal(gaps, stale, latest_trade)
            if sec_stale:
                self._heal_flow(min(sec_stale.values()))
        return ("error", detail)

    # ── 상태 전이 (알림 중복 방지) ──
    def _transition(self, status, detail):
        """상태 저장 후 (ok→bad)면 True. 복구(bad→ok)면 알림."""
        prev = self._load_state()
        changed = prev.get("status") != status
        if changed and status == "ok" and prev.get("status") == "bad":
            self.write_outbox("📊 데이터 신선도 복구: daily_prices 정상")
        os.makedirs(os.path.dirname(STATUS_PATH), exist_ok=True)
        with open(STATUS_PATH, "w") as f:
            json.dump({"status": status, "detail": detail,
                       "ts": datetime.now().isoformat(timespec="seconds")},
                      f, ensure_ascii=False)
        return changed and status == "bad"

    def _load_state(self):
        try:
            with open(STATUS_PATH) as f:
                return json.load(f)
        except Exception:
            return {}

    # ── 자동복구 (gap 최초 감지 시 1회) ──
    def _heal(self, gaps, stale, latest_trade):
        if os.environ.get("FRESHNESS_AUTOHEAL", "1") != "1":
            return
        hm = datetime.now().hour * 100 + datetime.now().minute
        if 1540 <= hm <= 1700:  # collector 수집 윈도우 충돌 방지
            self.log("collector 윈도우 — 자동복구 보류")
            return
        if subprocess.run(["pgrep", "-f", "backfill_kis_history.py"],
                          capture_output=True).returncode == 0:
            self.log("백필 이미 실행 중 — 자동복구 보류")
            return

        dates = [d for d, _ in gaps] + ([latest_trade] if stale else [])
        since = min(dates).replace("-", "")
        self.log(f"자동복구 시작: backfill --since {since}")
        heal_log = open(os.path.join(ROOT, "logs", "freshness_heal.log"), "a")
        subprocess.Popen(
            ["/usr/bin/python3", os.path.join(ROOT, "scripts", "backfill_kis_history.py"),
             "--since", since],
            cwd=ROOT, stdout=heal_log, stderr=subprocess.STDOUT,
        )

    # ── 보조테이블(수급/밸류/스크리닝) 자동복구 ──
    def _heal_flow(self, since):
        if os.environ.get("FRESHNESS_AUTOHEAL", "1") != "1":
            return
        hm = datetime.now().hour * 100 + datetime.now().minute
        if 1540 <= hm <= 1700:  # collector 수집 윈도우 충돌 방지
            self.log("collector 윈도우 — flow 자동복구 보류")
            return
        if subprocess.run(["pgrep", "-f", "backfill_flow.py"],
                          capture_output=True).returncode == 0:
            self.log("flow 백필 이미 실행 중 — 자동복구 보류")
            return
        self.log(f"flow 자동복구 시작: backfill_flow --since {since}")
        heal_log = open(os.path.join(ROOT, "logs", "freshness_heal.log"), "a")
        subprocess.Popen(
            ["/usr/bin/python3", os.path.join(ROOT, "scripts", "backfill_flow.py"),
             "--since", since],
            cwd=ROOT, stdout=heal_log, stderr=subprocess.STDOUT,
        )


if __name__ == "__main__":
    FreshnessMonitor().run()

"""미국 10년물 국채금리(^TNX) 모니터 — 매일 아침 루틴 보고 + 장중 변동 알림.

- 아침 보고: 매일 KST 07:30 이후 첫 폴링 1회 — 현재 금리·전일대비·52주 위치.
- 변동 알림: 기준가 대비 |Δ| ≥ 8bp 시 즉시 발신 (미 장중 실시간, 약 15분 지연).
- 폴링마다 daily_indices(US10Y)를 갱신 → /rates 페이지 자동 최신화.

데이터: src/treasury_yield.py (야후 ^TNX). 상태: run/treasury_state.json.
검증: TREASURY_RUN_NOW=1 로 1회 실행 (ALF_MY_NUMBER 미설정 시 콘솔 출력).
"""

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import market_db as db
import treasury_yield as ty
from monitor_base import MonitorBase

STATE_PATH = Path(__file__).resolve().parent.parent / "run" / "treasury_state.json"
CODE = "US10Y"
NAME = "미국 10년물 국채"
MORNING = (7, 30)     # KST 아침 보고 시각 (이후 첫 폴링 1회)
ALERT_BP = 8.0        # 기준가 대비 변동 알림 임계 (bp)


class TreasuryMonitor(MonitorBase):
    name = "treasury"
    interval = 900    # 15분 — 미 장중 변동 추적 (한국 낮엔 미장 휴장이라 변동 0)

    def check(self):
        q = ty.fetch_quote()
        if not q:
            return ("error", "야후 ^TNX 조회 실패")

        self._upsert_today(q)
        state = self._load_state()
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")

        # 1) 아침 루틴 보고 (KST 07:30 이후, 오늘 미보고)
        if (now.hour, now.minute) >= MORNING and state.get("last_report_date") != today:
            self.write_outbox(self._morning_msg(q), tag="treasury")
            state["last_report_date"] = today
            state["base_price"] = q["prev_close"]   # 그날 변동 기준 = 전일종가
            self._save_state(state)
            return ("ok", f"아침보고 {q['price']}% ({q['change_bp']:+.1f}bp)")

        # 2) 장중 변동 알림 (기준가 대비 ±ALERT_BP)
        base = state.get("base_price") or q["prev_close"]
        delta_bp = round((q["price"] - base) * 100, 1)
        if abs(delta_bp) >= ALERT_BP:
            self.write_outbox(self._alert_msg(q, base, delta_bp), tag="treasury")
            state["base_price"] = q["price"]         # 기준가 갱신 → 다음 ±8bp마다 재알림
            self._save_state(state)
            return ("ok", f"변동알림 {q['price']}% (기준대비 {delta_bp:+.1f}bp)")

        return ("ok", f"{q['price']}% (전일 {q['change_bp']:+.1f}bp, 기준대비 {delta_bp:+.1f}bp)")

    # ── 메시지 ────────────────────────────────────────
    def _morning_msg(self, q):
        arrow = "▲" if q["change_bp"] > 0 else "▼" if q["change_bp"] < 0 else "–"
        return (
            f"🇺🇸 미국 10년물 국채금리\n"
            f"{q['price']:.2f}%  {arrow} {abs(q['change_bp']):.1f}bp (전일 {q['prev_close']:.2f}%)\n"
            f"52주 {q['w52_low']:.2f}~{q['w52_high']:.2f}{self._w52_pos(q)}"
        )

    def _alert_msg(self, q, base, delta_bp):
        arrow = "▲" if delta_bp > 0 else "▼"
        return (
            f"⚠️ 미국 10년물 국채 급변 {arrow}{abs(delta_bp):.1f}bp\n"
            f"{q['price']:.2f}% (기준 {base:.2f}% 대비)\n"
            f"전일종가 대비 {q['change_bp']:+.1f}bp · 장중 실시간(~15분 지연)"
        )

    def _w52_pos(self, q):
        lo, hi, p = q.get("w52_low"), q.get("w52_high"), q["price"]
        if not lo or not hi or hi <= lo:
            return ""
        r = (p - lo) / (hi - lo)
        return " · 상단권" if r >= 0.8 else " · 하단권" if r <= 0.2 else " · 중단권"

    # ── 상태/저장 ─────────────────────────────────────
    def _upsert_today(self, q):
        """최신 금리를 daily_indices에 반영 (페이지 최신화). 날짜는 미 거래일."""
        d = q.get("as_of") or datetime.now().strftime("%Y-%m-%d")
        prev = q["prev_close"]
        try:
            db.upsert_daily_indices([{
                "code": CODE, "name": NAME, "date": d, "close": q["price"],
                "change": round(q["price"] - prev, 4),
                "change_rate": round((q["price"] - prev) / prev * 100, 4) if prev else None,
                "volume": None, "trade_value": None,
            }])
        except Exception as e:
            self.log(f"daily_indices 갱신 실패: {e}")

    def _load_state(self):
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_state(self, state):
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    TreasuryMonitor().run()

"""매수 타이밍 포착 데몬 — 장 마감 후 등록된 종목의 목표가 도달 시 iMessage 알림."""

import sys
from datetime import date
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import market_db as db
from monitor_base import MonitorBase

ALERTS_PATH = Path(__file__).resolve().parent.parent / "data" / "buy_alerts.yaml"
TRIGGER_TIME = 1640


class BuyAlertDaemon(MonitorBase):
    name = "buy-alert"
    interval = 30
    weekday_only = True

    def on_start(self):
        self._triggered = False

    def check(self):
        from datetime import datetime
        hm = datetime.now().hour * 100 + datetime.now().minute

        if hm < 100:
            self._triggered = False

        if hm >= TRIGGER_TIME and not self._triggered:
            self._triggered = True
            self._check_alerts()
            return "체크 완료"

        return f"대기 (triggered={self._triggered})"

    # ── private ───────────────────────────────────────

    def _check_alerts(self):
        alerts = _load_alerts()
        if not alerts:
            self.log("등록된 알림 없음")
            return

        triggered_any = False
        for alert in alerts:
            if not alert.get("enabled", True):
                continue
            if _is_expired(alert):
                continue

            code = alert["code"]
            close, price_date = _get_latest_close(code)
            if close is None:
                self.log(f"{alert['name']} ({code}): 시세 없음")
                continue

            self.log(f"{alert['name']}: 종가 {close:,.0f} / 목표 ≤{alert['price_low']:,.0f}")

            if close <= alert["price_low"]:
                self.write_outbox(_build_message(alert, close, price_date))
                alert["enabled"] = False
                triggered_any = True
                self.log(f"** {alert['name']} 조건 충족! **")

        if triggered_any:
            _save_alerts(alerts)


# ── helpers ───────────────────────────────────────────

def _load_alerts():
    if not ALERTS_PATH.exists():
        return []
    data = yaml.safe_load(ALERTS_PATH.read_text(encoding="utf-8"))
    return (data or {}).get("alerts", [])


def _save_alerts(alerts):
    ALERTS_PATH.write_text(
        yaml.dump({"alerts": alerts}, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )


def _is_expired(alert):
    expires = alert.get("expires")
    if not expires:
        return False
    if isinstance(expires, date):
        return date.today() > expires
    return date.today() > date.fromisoformat(str(expires))


def _get_latest_close(code):
    try:
        rows = db.get_daily_prices(code, limit=1)
    except Exception:
        return None, None
    if not rows:
        return None, None
    return rows[0]["close"], rows[0]["date"]


def _build_message(alert, close, price_date):
    lines = [
        f"[매수 시그널] {alert['name']} ({alert['code']})",
        "",
        f"종가: {close:,.0f}원 ({price_date})",
        f"목표: {alert['price_low']:,.0f}원 이하",
    ]
    if alert.get("price_high"):
        lines.append(f"범위: {alert['price_low']:,.0f}~{alert['price_high']:,.0f}원")
    lines.append(f"사유: {alert.get('reason', '-')}")
    lines.append(f"전략: {alert.get('strategy', '-')}")
    lines.append(f"등록일: {alert.get('registered', '-')}")
    return "\n".join(lines)


if __name__ == "__main__":
    BuyAlertDaemon().run()

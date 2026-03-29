#!/usr/bin/env python3
"""매수 타이밍 포착 데몬 — 장 마감 후 등록된 종목의 목표가 도달 시 iMessage 알림.

수집 스케줄 (평일):
  16:40  buy_alerts.yaml 로드 → market.db 종가 체크 → 조건 충족 시 outbox 알림

환경변수:
  BUY_ALERT_RUN_NOW=1  (즉시 1회 실행, 테스트용)
"""

import json
import os
import sys
import time
import traceback
from datetime import datetime, date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import market_db as db

ALERTS_PATH = ROOT / "data" / "buy_alerts.yaml"
OUTBOX = ROOT / "run" / "outbox"
RECIPIENT = os.environ["ALF_MY_NUMBER"]

TRIGGER_TIME = 1640  # 16:40
POLL_INTERVAL = 30


def log(msg):
    print(f"[buy-alert {datetime.now():%H:%M:%S}] {msg}", flush=True)


def load_alerts():
    """buy_alerts.yaml 로드. 파일 없거나 비어있으면 빈 리스트."""
    if not ALERTS_PATH.exists():
        return []
    data = yaml.safe_load(ALERTS_PATH.read_text(encoding="utf-8"))
    if not data or not data.get("alerts"):
        return []
    return data["alerts"]


def save_alerts(alerts):
    """buy_alerts.yaml 저장."""
    data = {"alerts": alerts}
    ALERTS_PATH.write_text(
        yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )


def is_expired(alert):
    """유효기간 초과 여부."""
    expires = alert.get("expires")
    if not expires:
        return False
    if isinstance(expires, date):
        return date.today() > expires
    return date.today() > date.fromisoformat(str(expires))


def get_latest_close(code):
    """market.db에서 최신 종가 조회. 없으면 None."""
    try:
        rows = db.get_daily_prices(code, limit=1)
    except Exception:
        return None, None
    if not rows:
        return None, None
    row = rows[0]
    return row["close"], row["date"]


def format_price(price):
    """가격을 읽기 쉽게 포맷."""
    return f"{price:,.0f}"


def build_message(alert, close, price_date):
    """알림 메시지 생성."""
    lines = [
        f"[매수 시그널] {alert['name']} ({alert['code']})",
        "",
        f"종가: {format_price(close)}원 ({price_date})",
        f"목표: {format_price(alert['price_low'])}원 이하",
    ]
    if alert.get("price_high"):
        lines.append(f"범위: {format_price(alert['price_low'])}~{format_price(alert['price_high'])}원")
    lines.append(f"사유: {alert.get('reason', '-')}")
    lines.append(f"전략: {alert.get('strategy', '-')}")
    lines.append(f"등록일: {alert.get('registered', '-')}")
    return "\n".join(lines)


def send_alert(message):
    """outbox에 JSON 작성 → bridge가 iMessage 전송."""
    OUTBOX.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    payload = {
        "recipient": RECIPIENT,
        "message": message,
        "timestamp": datetime.now().isoformat(),
    }
    path = OUTBOX / f"{ts}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    log(f"알림 전송: {path.name}")


def check_alerts():
    """등록된 알림 조건 체크 → 충족 시 알림 전송."""
    alerts = load_alerts()
    if not alerts:
        log("등록된 알림 없음")
        return

    triggered_any = False
    for alert in alerts:
        if not alert.get("enabled", True):
            continue
        if is_expired(alert):
            continue

        code = alert["code"]
        price_low = alert["price_low"]
        close, price_date = get_latest_close(code)

        if close is None:
            log(f"{alert['name']} ({code}): 시세 데이터 없음")
            continue

        log(f"{alert['name']}: 종가 {format_price(close)} / 목표 ≤{format_price(price_low)}")

        if close <= price_low:
            msg = build_message(alert, close, price_date)
            send_alert(msg)
            alert["enabled"] = False
            triggered_any = True
            log(f"** {alert['name']} 조건 충족! 알림 발송 **")

    if triggered_any:
        save_alerts(alerts)


def run():
    """메인 루프."""
    log("데몬 시작")
    triggered_today = False

    if os.environ.get("BUY_ALERT_RUN_NOW"):
        log("즉시 실행 모드")
        check_alerts()
        log("즉시 실행 완료")
        return

    while True:
        try:
            now = datetime.now()
            hm = now.hour * 100 + now.minute
            is_weekday = now.weekday() < 5

            if is_weekday and hm >= TRIGGER_TIME and not triggered_today:
                triggered_today = True
                log("장 마감 체크 시작")
                check_alerts()
                log("장 마감 체크 완료")

            if hm < 100:
                triggered_today = False

        except Exception:
            log(f"오류:\n{traceback.format_exc()}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    run()

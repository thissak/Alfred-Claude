"""heartbeat.py — 데몬 heartbeat 기록 유틸리티.

각 데몬이 beat()를 호출하면 run/heartbeat/{name}.json에 타임스탬프 기록.
대시보드는 이 파일들의 mtime으로 생사 판단.
"""

import json
import os
from datetime import datetime

_HEARTBEAT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "run", "heartbeat"
)


def beat(name: str, status: str = "ok", detail: str = ""):
    """Heartbeat 1회 기록.

    Args:
        name: 데몬 이름 (daemon_ctl.py의 키와 동일)
        status: "ok" | "error" | "idle"
        detail: 최근 활동 요약 (예: "수집 완료 3종목")
    """
    os.makedirs(_HEARTBEAT_DIR, exist_ok=True)
    path = os.path.join(_HEARTBEAT_DIR, f"{name}.json")
    data = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "detail": detail,
    }
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False)

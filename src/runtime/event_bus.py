"""경량 이벤트 버스 헬퍼.

현재는 inbox 메시지를 공통 이벤트 구조로 정규화하는 역할만 맡는다.
향후 이벤트 저장/중복 방지/재처리 로직을 여기에 확장한다.
"""

from datetime import datetime


def build_message_received(msg):
    """inbox JSON을 정규화된 message.received 이벤트로 변환."""
    ts = msg.get("timestamp") or datetime.now().isoformat()
    source_path = msg.get("_path", "")

    return {
        "id": f"evt:{source_path or ts}",
        "type": "message.received",
        "channel": "imessage",
        "sender": msg["sender"],
        "text": msg["message"],
        "ts": ts,
        "source_path": source_path,
        "raw": msg,
    }

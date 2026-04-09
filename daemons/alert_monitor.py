#!/usr/bin/env python3
"""GCP Alert 모니터 — Pub/Sub Pull → Claude 분석 → iMessage 알림.

동작: Pub/Sub에서 GCP Alert 메시지 수신 → claude -p로 분석 → outbox → iMessage
인증: health-monitor-reader 서비스 계정 (Pub/Sub subscriber 권한 필요)

사용법:
  python daemons/alert_monitor.py                    # 데몬 모드
  ALERT_RUN_NOW=1 python daemons/alert_monitor.py    # 즉시 1회 pull 후 종료

환경변수:
  ALF_MY_NUMBER     — iMessage 수신자 (필수)
  ALERT_INTERVAL    — pull 간격 초 (기본 30)
  ALERT_RUN_NOW     — 1이면 즉시 1회 실행 후 종료
"""

import json
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTBOX = ROOT / "run" / "outbox"
KEY_FILE = ROOT / "config" / "health-monitor-key.json"

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

sys.path.insert(0, str(ROOT / "src"))
from heartbeat import beat

OWNER = os.environ.get("ALF_MY_NUMBER", "")          # 내 번호 (분석 포함)
CLIENT = os.environ.get("ALERT_CLIENT_NUMBER", "")    # 고객 번호 (단순 알림만)
POLL_INTERVAL = int(os.environ.get("ALERT_INTERVAL", "30"))
CLAUDE_CLI = "/Users/afred/.local/bin/claude"

# Pub/Sub 구독 (프로젝트별)
SUBSCRIPTIONS = [
    "projects/taxlaw-db-api/subscriptions/gcp-alerts-macmini",
    "projects/etaxbook-web/subscriptions/gcp-alerts-macmini",
]

SYSTEM_PROMPT = """\
너는 GCP 인프라 장애 분석 전문가다. 아래 프로젝트 구조를 참고하여 GCP Alert을 분석해.

## 프로젝트 구조
- etaxbook-web: Cloud Run (etaxbook-nts, etaxbook-ebook) + Cloud SQL + GCS + Load Balancer
- taxlaw-db-api: Cloud Run (etaxbook-taxlaw-api) + Compute Engine (es-taxlaw, ES VM) + Cloud SQL

## Alert 유형
- Cloud Run 5xx: 서버 에러 — 최근 배포 확인, 로그 확인 필요
- Cloud Run 응답 지연: 콜드스타트 or 과부하 — 인스턴스 수 확인
- Cloud Run 트래픽 급증: DDoS or 크롤러 — 트래픽 패턴 확인
- ES GCE CPU/Memory/Disk: VM 리소스 부족 — 스케일업 or 인덱스 최적화
- ES GCE Uptime: ES 서비스 다운 — VM 상태, ES 프로세스 확인

## 출력 규칙
- 300자 이내 핵심만
- 심각도 판별: [긴급] / [주의] / [참고]
- 원인 추정 + 즉시 조치 가능한 것 제시
- 한국어로 답변
"""


def log(msg):
    print(f"[alert {datetime.now():%H:%M:%S}] {msg}", flush=True)


# ── Pub/Sub Pull ─────────────────────────────────────

def pull_messages():
    """모든 구독에서 메시지 pull. Returns list of parsed alert dicts."""
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(KEY_FILE)

    from google.cloud import pubsub_v1
    alerts = []

    for sub_path in SUBSCRIPTIONS:
        project = sub_path.split("/")[1]
        try:
            client = pubsub_v1.SubscriberClient()
            response = client.pull(
                subscription=sub_path,
                max_messages=10,
                timeout=10,
            )

            if not response.received_messages:
                continue

            ack_ids = []
            for msg in response.received_messages:
                ack_ids.append(msg.ack_id)
                try:
                    data = json.loads(msg.message.data.decode("utf-8"))
                    data["_project"] = project
                    alerts.append(data)
                    log(f"수신: {project} — {data.get('incident', {}).get('policy_name', '?')}")
                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    log(f"파싱 실패: {e}")
                    alerts.append({
                        "_project": project,
                        "_raw": msg.message.data.decode("utf-8", errors="replace")[:500],
                    })

            # ACK
            if ack_ids:
                client.acknowledge(subscription=sub_path, ack_ids=ack_ids)
                log(f"ACK: {project} — {len(ack_ids)}건")

        except Exception as e:
            # 504 Deadline은 메시지 없음 — 정상 동작이므로 무시
            if "504" not in str(e) and "Deadline" not in str(e):
                log(f"pull 실패 ({project}): {e}")

    return alerts


# ── Claude 분석 ──────────────────────────────────────

def format_alert_summary(alert):
    """Alert JSON을 사람이 읽을 수 있는 요약으로 변환."""
    incident = alert.get("incident", {})
    state = incident.get("state", "unknown")
    policy = incident.get("policy_name", "알 수 없는 정책")
    summary = incident.get("summary", "")
    resource = incident.get("resource", {})
    resource_name = resource.get("labels", {}).get("service_name", "") or \
                    resource.get("labels", {}).get("instance_id", "") or \
                    resource.get("type", "")
    condition = incident.get("condition_name", "")
    url = incident.get("url", "")
    project = alert.get("_project", "")

    lines = [
        f"프로젝트: {project}",
        f"정책: {policy}",
        f"상태: {state}",
        f"조건: {condition}",
        f"리소스: {resource_name}",
        f"요약: {summary}",
    ]
    if url:
        lines.append(f"URL: {url}")

    return "\n".join(lines)


def ask_claude(alert_text):
    """claude -p로 Alert 분석 요청."""
    prompt = f"""\
다음 GCP Alert이 발생했다. 분석해줘.

시각: {datetime.now().strftime('%Y-%m-%d %H:%M KST')}

{alert_text}

원인을 분석하고 심각도와 조치 방법을 알려줘. 300자 이내."""

    env = os.environ.copy()
    env["GOOGLE_APPLICATION_CREDENTIALS"] = str(KEY_FILE)
    env.pop("CLAUDECODE", None)

    cmd = [
        CLAUDE_CLI, "-p",
        "--model", "sonnet",
        "--output-format", "json",
        "--max-turns", "3",
        "--allowedTools", "Bash",
        "--system-prompt", SYSTEM_PROMPT,
        prompt,
    ]
    log("claude -p 분석 시작...")

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120, env=env,
        )
        if result.returncode != 0:
            log(f"claude 에러: {result.stderr.strip()[:100]}")
            return None
        data = json.loads(result.stdout)
        return data.get("result", "")
    except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        log(f"claude 실패: {e}")
        return None


# ── 알림 ─────────────────────────────────────────────

def write_outbox(recipient, message):
    """outbox JSON 생성 → alf_bridge가 iMessage 발신."""
    if not recipient:
        return

    OUTBOX.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    # 같은 시각에 두 건 생성될 수 있으므로 recipient 해시 추가
    suffix = "owner" if recipient == OWNER else "client"
    payload = {
        "recipient": recipient,
        "message": message,
        "timestamp": datetime.now().isoformat(),
    }
    path = OUTBOX / f"alert_{ts}_{suffix}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    log(f"outbox ({suffix}): {path.name}")


# ── 메인 처리 ────────────────────────────────────────

def process_alerts():
    """Pub/Sub pull → 분석 → 알림. Returns: 처리 건수."""
    alerts = pull_messages()
    if not alerts:
        return 0

    for alert in alerts:
        incident = alert.get("incident", {})
        state = incident.get("state", "unknown")
        policy = incident.get("policy_name", "?")

        # Alert 요약
        alert_text = format_alert_summary(alert)

        if state == "open":
            # 고객: 단순 알림
            client_msg = f"[GCP Alert] {policy}\n{alert_text}"
            write_outbox(CLIENT, client_msg)

            # 나: Claude 분석 포함
            analysis = ask_claude(alert_text)
            owner_lines = [f"[GCP Alert] {policy}", alert_text]
            if analysis:
                owner_lines += ["", "== Claude 분석 ==", analysis]
            write_outbox(OWNER, "\n".join(owner_lines))

        elif state == "closed":
            now = datetime.now().strftime("%H:%M KST")
            closed_msg = f"[GCP 복구] {policy} ({now})\n{alert_text}"
            write_outbox(CLIENT, closed_msg)
            write_outbox(OWNER, closed_msg)

        else:
            other_msg = f"[GCP Alert] {state}: {policy}\n{alert_text}"
            write_outbox(CLIENT, other_msg)
            write_outbox(OWNER, other_msg)

    return len(alerts)


# ── 데몬 루프 ────────────────────────────────────────

def run():
    log(f"GCP Alert 모니터 시작 (interval={POLL_INTERVAL}s)")
    log(f"구독: {len(SUBSCRIPTIONS)}개")
    log(f"내 번호: {OWNER or '(미설정)'}")
    log(f"고객 번호: {CLIENT or '(미설정)'}")
    log(f"키 파일: {'존재' if KEY_FILE.exists() else '없음!'}")

    beat("alert", "ok", "시작됨")

    # 즉시 실행 모드
    if os.environ.get("ALERT_RUN_NOW") == "1":
        n = process_alerts()
        beat("alert", "ok", f"즉시 실행 완료 ({n}건)")
        return

    while True:
        try:
            n = process_alerts()
            status = f"{n}건 처리" if n else "대기"
            beat("alert", "ok", status)
            time.sleep(POLL_INTERVAL)
        except KeyboardInterrupt:
            log("종료")
            break
        except Exception as e:
            beat("alert", "error", str(e)[:100])
            log(f"에러: {e}")
            traceback.print_exc()
            time.sleep(60)


if __name__ == "__main__":
    run()

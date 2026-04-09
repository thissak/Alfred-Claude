"""GCP Alert 모니터 — Pub/Sub Pull → Claude 분석 → iMessage 알림.

동작: Pub/Sub에서 GCP Alert 메시지 수신 → claude -p로 분석 → outbox → iMessage
인증: health-monitor-reader 서비스 계정 (Pub/Sub subscriber 권한 필요)
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from monitor_base import MonitorBase

KEY_FILE = Path(__file__).resolve().parent.parent / "config" / "health-monitor-key.json"

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


class AlertMonitor(MonitorBase):
    name = "alert"
    interval = 30
    claude_model = "sonnet"
    claude_max_turns = 3
    claude_tools = "Bash"
    claude_system_prompt = SYSTEM_PROMPT

    def on_start(self):
        self.client = os.environ.get("ALERT_CLIENT_NUMBER", "")
        self.log(f"구독: {len(SUBSCRIPTIONS)}개")
        self.log(f"고객 번호: {self.client or '(미설정)'}")
        self.log(f"키 파일: {'존재' if KEY_FILE.exists() else '없음!'}")

    def claude_extra_env(self):
        return {"GOOGLE_APPLICATION_CREDENTIALS": str(KEY_FILE)}

    def check(self):
        alerts = self._pull_messages()
        if not alerts:
            return "대기"

        for alert in alerts:
            incident = alert.get("incident", {})
            state = incident.get("state", "unknown")
            policy = incident.get("policy_name", "?")
            alert_text = _format_alert_summary(alert)

            if state == "open":
                # 고객: 단순 알림
                self.write_outbox(
                    f"[GCP Alert] {policy}\n{alert_text}",
                    recipient=self.client, tag="alert_client",
                )
                # 나: Claude 분석 포함
                prompt = (
                    f"다음 GCP Alert이 발생했다. 분석해줘.\n\n"
                    f"시각: {datetime.now().strftime('%Y-%m-%d %H:%M KST')}\n\n"
                    f"{alert_text}\n\n원인 분석 + 심각도 + 조치 방법. 300자 이내."
                )
                analysis = self.ask_claude(prompt)
                analysis_text = analysis if isinstance(analysis, str) else str(analysis or "")
                lines = [f"[GCP Alert] {policy}", alert_text]
                if analysis_text:
                    lines += ["", "== Claude 분석 ==", analysis_text]
                self.write_outbox("\n".join(lines), tag="alert_owner")

            elif state == "closed":
                now_str = datetime.now().strftime("%H:%M KST")
                msg = f"[GCP 복구] {policy} ({now_str})\n{alert_text}"
                self.write_outbox(msg, recipient=self.client, tag="alert_client")
                self.write_outbox(msg, tag="alert_owner")

            else:
                msg = f"[GCP Alert] {state}: {policy}\n{alert_text}"
                self.write_outbox(msg, recipient=self.client, tag="alert_client")
                self.write_outbox(msg, tag="alert_owner")

        return f"{len(alerts)}건 처리"

    # ── private ───────────────────────────────────────

    def _pull_messages(self):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(KEY_FILE)
        from google.cloud import pubsub_v1

        alerts = []
        for sub_path in SUBSCRIPTIONS:
            project = sub_path.split("/")[1]
            try:
                client = pubsub_v1.SubscriberClient()
                response = client.pull(subscription=sub_path, max_messages=10, timeout=10)
                if not response.received_messages:
                    continue

                ack_ids = []
                for msg in response.received_messages:
                    ack_ids.append(msg.ack_id)
                    try:
                        data = json.loads(msg.message.data.decode("utf-8"))
                        data["_project"] = project
                        alerts.append(data)
                        self.log(f"수신: {project} — {data.get('incident', {}).get('policy_name', '?')}")
                    except (json.JSONDecodeError, UnicodeDecodeError) as e:
                        self.log(f"파싱 실패: {e}")
                        alerts.append({
                            "_project": project,
                            "_raw": msg.message.data.decode("utf-8", errors="replace")[:500],
                        })

                if ack_ids:
                    client.acknowledge(subscription=sub_path, ack_ids=ack_ids)
                    self.log(f"ACK: {project} — {len(ack_ids)}건")

            except Exception as e:
                if "504" not in str(e) and "Deadline" not in str(e):
                    self.log(f"pull 실패 ({project}): {e}")

        return alerts


def _format_alert_summary(alert):
    incident = alert.get("incident", {})
    resource = incident.get("resource", {})
    resource_name = (resource.get("labels", {}).get("service_name", "")
                     or resource.get("labels", {}).get("instance_id", "")
                     or resource.get("type", ""))
    lines = [
        f"프로젝트: {alert.get('_project', '')}",
        f"정책: {incident.get('policy_name', '알 수 없는 정책')}",
        f"상태: {incident.get('state', 'unknown')}",
        f"조건: {incident.get('condition_name', '')}",
        f"리소스: {resource_name}",
        f"요약: {incident.get('summary', '')}",
    ]
    url = incident.get("url", "")
    if url:
        lines.append(f"URL: {url}")
    return "\n".join(lines)


if __name__ == "__main__":
    AlertMonitor().run()

"""GCP 헬스 모니터 — HTTP 헬스체크 + gcloud 진단 + Claude 분석 → iMessage 알림.

동작: 5분 간격 폴링 → 장애 감지 → gcloud 진단 수집 → claude -p 분석 → outbox → iMessage
인증: read-only 서비스 계정 (health-monitor-reader@etaxbook-web.iam.gserviceaccount.com)
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from monitor_base import MonitorBase

KEY_FILE = Path(__file__).resolve().parent.parent / "config" / "health-monitor-key.json"

ENDPOINTS = [
    {"name": "NTS", "url": "https://nts.etaxbook.co.kr/health",
     "project": "etaxbook-web", "service": "etaxbook-nts"},
    {"name": "eBook", "url": "https://etaxbook.co.kr/health",
     "project": "etaxbook-web", "service": "etaxbook-ebook"},
    {"name": "Taxlaw API", "url": "https://taxlaw.etaxbook.co.kr/health",
     "project": "taxlaw-db-api", "service": "etaxbook-taxlaw-api"},
    {"name": "ES (검색)", "url": "https://taxlaw.etaxbook.co.kr/api/search?q=test&size=1",
     "project": "taxlaw-db-api", "service": "etaxbook-taxlaw-api"},
]

SYSTEM_PROMPT = """\
너는 GCP 인프라 장애 분석 전문가다. 모니터가 보고한 장애가 실제 장애인지, 아니면 모니터 측 오탐(false positive)인지 먼저 판정한다.

## 프로젝트 구조
- etaxbook-web: Cloud Run (etaxbook-nts, etaxbook-ebook) + Cloud SQL + GCS + Load Balancer
- taxlaw-db-api: Cloud Run (etaxbook-taxlaw-api) + Compute Engine (es-taxlaw, ES VM) + Cloud SQL

## 오탐 판정 프로토콜 (필수, 최우선)
모니터는 맥미니 python-requests 기반 외부 프로브다. LibreSSL+urllib3 호환 이슈, apex DNS glitch, 로컬 네트워크 blip 등으로 오탐이 발생할 수 있다.

판정 순서:
1. 제공된 진단 결과의 "Cloud Run 로그 (최근 10분)" 블록을 확인한다.
2. 장애 시각 전후에 **다른 사용자 트래픽이 200 OK로 처리**되었는가?
3. 같은 시각에 **ERROR/WARNING 로그가 없는가?**
4. Cloud Run 서비스가 Ready 상태이고 billing 정상인가?
5. 동일 LB/프로젝트의 **다른 엔드포인트가 정상**이었는가?

위 조건이 모두 충족되면 서버는 정상 동작 중이므로 **오탐**이다.

## 출력 형식 (엄격)
반드시 첫 줄을 아래 둘 중 하나로 시작한다:
- `[VERDICT: FALSE_POSITIVE]` — 오탐으로 판정한 경우
- `[VERDICT: REAL]` — 실제 장애로 판정한 경우

그 다음 줄부터 판정 근거(한 줄) + 조치 방법. 전체 300자 이내. 한국어.
"""


class HealthMonitor(MonitorBase):
    name = "health"
    interval = 300
    claude_model = "sonnet"
    claude_max_turns = 3
    claude_tools = "Bash"
    claude_system_prompt = SYSTEM_PROMPT

    def on_start(self):
        self._state_file = self.root / "run" / "health_status.json"
        self.log(f"엔드포인트: {len(ENDPOINTS)}개")
        self.log(f"키 파일: {'존재' if KEY_FILE.exists() else '없음!'}")

    def claude_extra_env(self):
        return {"GOOGLE_APPLICATION_CREDENTIALS": str(KEY_FILE)}

    def check(self):
        last_status = self._load_status()
        current = {}
        results = []

        for ep in ENDPOINTS:
            name, healthy, elapsed, error = self._check_endpoint(ep)
            results.append((name, healthy, elapsed, error))
            current[name] = {
                "healthy": healthy, "elapsed": round(elapsed, 2),
                "error": error, "checked_at": datetime.now().isoformat(),
            }

        newly_down = []
        newly_up = []
        for name, healthy, elapsed, error in results:
            was_healthy = last_status.get(name, {}).get("healthy", True)
            if was_healthy and not healthy:
                newly_down.append((name, error))
                self.log(f"DOWN: {name} — {error}")
            elif not was_healthy and healthy:
                newly_up.append((name, elapsed))
                self.log(f"UP: {name} ({elapsed:.2f}s)")
            elif healthy:
                self.log(f"ok: {name} ({elapsed:.2f}s)")
            else:
                self.log(f"still down: {name}")

        alerts = 0
        if newly_down:
            alerts += self._handle_down(newly_down, results)
        if newly_up:
            alerts += self._handle_up(newly_up, results)

        self._save_status(current)
        return f"{len(newly_down)} down, {len(newly_up)} up, {alerts}알림"

    # ── private ───────────────────────────────────────

    def _check_endpoint(self, ep):
        try:
            start = time.time()
            r = requests.get(ep["url"], timeout=10)
            elapsed = time.time() - start
            healthy = r.status_code == 200
            return ep["name"], healthy, elapsed, None if healthy else f"HTTP {r.status_code}"
        except requests.RequestException as e:
            return ep["name"], False, 0, str(e)[:200]

    def _handle_down(self, newly_down, results):
        failed_names = [n for n, _ in newly_down]
        now_str = datetime.now().strftime("%H:%M KST")

        self.log("gcloud 진단 수집 중...")
        diagnostics = self._collect_diagnostics(failed_names)

        prompt = (
            f"모니터가 다음 엔드포인트의 장애를 보고했다:\n"
            f"- 장애: {', '.join(failed_names)}\n"
            f"- 시각: {datetime.now().strftime('%Y-%m-%d %H:%M KST')}\n\n"
            f"진단 결과:\n```\n{diagnostics}\n```\n\n"
            f"오탐/실장애 판정 + 근거 + 조치. 첫 줄 [VERDICT: ...] 필수."
        )
        analysis = self.ask_claude(prompt)
        analysis_text = analysis if isinstance(analysis, str) else str(analysis or "")
        verdict = "FALSE_POSITIVE" if "[VERDICT: FALSE_POSITIVE]" in analysis_text else "REAL"
        self.log(f"판정: {verdict}")

        title = f"[오탐 의심] {', '.join(failed_names)} ({now_str})" if verdict == "FALSE_POSITIVE" \
            else f"[GCP 장애] {', '.join(failed_names)} ({now_str})"
        lines = [title]
        for name, error in newly_down:
            lines.append(f"  - {name}: {error}")
        if analysis_text:
            lines += ["", "== Claude 분석 ==", analysis_text]
        else:
            lines += ["", "== 진단 ==", diagnostics[:500]]

        self.write_outbox("\n".join(lines), tag="health")
        return 1

    def _handle_up(self, newly_up, results):
        now_str = datetime.now().strftime("%H:%M KST")
        lines = [f"[GCP 복구] ({now_str})"]
        for name, elapsed in newly_up:
            lines.append(f"  - {name}: 200 OK ({elapsed:.1f}s)")
        still_down = [n for n, h, _, _ in results if not h and n not in [x[0] for x in newly_up]]
        if still_down:
            lines.append(f"  - 아직 장애: {', '.join(still_down)}")
        self.write_outbox("\n".join(lines), tag="health")
        return 1

    def _collect_diagnostics(self, failed_names):
        projects = set(ep["project"] for ep in ENDPOINTS if ep["name"] in failed_names)
        diag = []
        for proj in projects:
            diag.append(f"=== {proj} ===")
            diag.append("# billing")
            diag.append(_run_gcloud(["gcloud", "billing", "projects", "describe", proj]))
            diag.append("# cloud run")
            diag.append(_run_gcloud([
                "gcloud", "run", "services", "list", f"--project={proj}",
                "--region=asia-northeast3", "--format=table(SERVICE,STATUS,URL)",
            ]))
            if proj == "taxlaw-db-api":
                diag.append("# compute engine")
                diag.append(_run_gcloud([
                    "gcloud", "compute", "instances", "list", f"--project={proj}",
                    "--format=table(NAME,ZONE,STATUS)",
                ]))

        for ep in ENDPOINTS:
            if ep["name"] not in failed_names:
                continue
            diag.append(f"# {ep['name']} Cloud Run 로그 (최근 10분)")
            diag.append(_fetch_cloud_run_logs(ep["service"], ep["project"]))

        ok_names = [ep["name"] for ep in ENDPOINTS if ep["name"] not in failed_names]
        if ok_names:
            diag.append(f"# 같은 시각 정상 엔드포인트: {', '.join(ok_names)}")
        return "\n".join(diag)

    def _load_status(self):
        if self._state_file.exists():
            return json.loads(self._state_file.read_text())
        return {}

    def _save_status(self, status):
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._state_file.write_text(json.dumps(status, ensure_ascii=False, indent=2))


# ── gcloud helpers ────────────────────────────────────

def _run_gcloud(cmd):
    env = os.environ.copy()
    env["GOOGLE_APPLICATION_CREDENTIALS"] = str(KEY_FILE)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=env)
        return result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
    except subprocess.TimeoutExpired:
        return "(timeout)"


def _fetch_cloud_run_logs(service, project, minutes=10):
    now_utc = datetime.utcnow()
    start = (now_utc - timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")

    ok_filter = (
        f'resource.type="cloud_run_revision" '
        f'resource.labels.service_name="{service}" '
        f'timestamp>="{start}" '
        f'httpRequest.status>=200 httpRequest.status<400'
    )
    ok_out = _run_gcloud([
        "gcloud", "logging", "read", ok_filter,
        f"--project={project}", "--limit=50",
        "--format=value(timestamp,httpRequest.requestUrl)",
    ])
    ok_lines = [l for l in ok_out.splitlines() if l.strip()]

    err_filter = (
        f'resource.type="cloud_run_revision" '
        f'resource.labels.service_name="{service}" '
        f'timestamp>="{start}" '
        f'severity>="ERROR"'
    )
    err_out = _run_gcloud([
        "gcloud", "logging", "read", err_filter,
        f"--project={project}", "--limit=5",
        "--format=value(timestamp,severity,textPayload)",
    ])

    lines = [f"  최근 {minutes}분 정상 응답(2xx/3xx) 건수: {len(ok_lines)}"]
    if ok_lines:
        lines.append(f"  샘플: {ok_lines[0][:120]}")
    lines.append(f"  ERROR 로그: {'없음' if not err_out.strip() else err_out[:400]}")
    return "\n".join(lines)


if __name__ == "__main__":
    HealthMonitor().run()

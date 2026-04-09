"""monitor_base.py — 모니터링 데몬 공통 베이스 클래스.

모든 모니터링 데몬이 이 클래스를 상속한다.
서브클래스는 check() 메서드 하나만 구현하면 동작.

공통 인프라:
  - 데몬 루프 (폴링, sleep, 에러 처리)
  - 시간 게이트 (weekday_only, time_gate)
  - RUN_NOW 즉시 실행 모드
  - ask_claude() — claude -p 호출 + JSON 파싱
  - write_outbox() — outbox JSON 생성
  - heartbeat, 로깅
"""

import json
import os
import re
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from heartbeat import beat

CLAUDE_CLI = "/Users/afred/.local/bin/claude"


class MonitorBase:
    """모니터링 데몬 베이스. 서브클래스는 check()만 구현."""

    # ── 서브클래스가 설정 ──────────────────────────────
    name: str = ""
    interval: int = 300
    weekday_only: bool = False
    time_gate: tuple = None       # (900, 1530) 형태. None이면 항시 가동

    # Claude 설정 (claude_model이 None이면 ask_claude 사용 불가)
    claude_model: str = None
    claude_max_turns: int = 1
    claude_tools: str = ""        # "" 또는 "Bash"
    claude_system_prompt: str = ""

    def __init__(self):
        self.root = ROOT
        self.outbox_dir = ROOT / "run" / "outbox"
        prefix = self.name.upper().replace("-", "_")
        self.interval = int(os.environ.get(f"{prefix}_INTERVAL", str(self.interval)))
        self._run_now = os.environ.get(f"{prefix}_RUN_NOW") == "1"
        self.recipient = os.environ.get("ALF_MY_NUMBER", "")

    # ── 서브클래스가 반드시 구현 ──────────────────────
    def check(self) -> str:
        """1회 체크. heartbeat detail로 사용할 상태 문자열 반환."""
        raise NotImplementedError

    # ── 서브클래스가 선택적 오버라이드 ────────────────
    def on_start(self):
        """루프 진입 전 초기화."""
        pass

    def claude_extra_env(self) -> dict:
        """claude subprocess에 추가할 환경변수 (예: GCP 키)."""
        return {}

    # ── 내장 헬퍼 ─────────────────────────────────────
    def log(self, msg):
        print(f"[{self.name} {datetime.now():%H:%M:%S}] {msg}", flush=True)

    def ask_claude(self, prompt, system_prompt=None):
        """claude -p 호출. Returns: dict(JSON) | str(plain) | None(실패)."""
        env = os.environ.copy()
        env.pop("CLAUDECODE", None)
        env.update(self.claude_extra_env())

        cmd = [
            CLAUDE_CLI, "-p",
            "--model", self.claude_model or "sonnet",
            "--output-format", "json",
            "--max-turns", str(self.claude_max_turns),
            "--allowedTools", self.claude_tools,
            "--system-prompt", system_prompt or self.claude_system_prompt,
            prompt,
        ]
        self.log("claude -p 시작...")

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=120, env=env,
            )
            if result.returncode != 0:
                self.log(f"claude 에러: {result.stderr.strip()[:200]}")
                return None
            outer = json.loads(result.stdout)
            raw = (outer.get("result") or "").strip()
            # JSON 파싱 시도 (코드펜스 방어)
            try:
                if raw.startswith("```"):
                    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.DOTALL).strip()
                return json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                return raw
        except subprocess.TimeoutExpired:
            self.log("claude 타임아웃 (120s)")
            return None
        except (json.JSONDecodeError, KeyError) as e:
            self.log(f"claude 파싱 실패: {e}")
            return None

    def write_outbox(self, message, recipient=None, tag=None):
        """outbox JSON 생성 → alf_bridge가 iMessage 발신."""
        recipient = recipient or self.recipient
        if not recipient:
            self.log("수신자 미설정, 콘솔 출력만")
            print(message)
            return

        self.outbox_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        tag = tag or self.name
        payload = {
            "recipient": recipient,
            "message": message,
            "timestamp": datetime.now().isoformat(),
        }
        path = self.outbox_dir / f"{tag}_{ts}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
        self.log(f"outbox: {path.name}")

    def _in_time_window(self):
        now = datetime.now()
        if self.weekday_only and now.weekday() >= 5:
            return False
        if self.time_gate:
            hm = now.hour * 100 + now.minute
            return self.time_gate[0] <= hm <= self.time_gate[1]
        return True

    # ── 데몬 루프 ─────────────────────────────────────
    def run(self):
        self.log(f"{self.name} 시작 (interval={self.interval}s)")
        beat(self.name, "ok", "시작됨")
        self.on_start()

        if self._run_now:
            status = self.check()
            beat(self.name, "ok", f"즉시 실행: {status}")
            return

        while True:
            try:
                if self._in_time_window():
                    status = self.check()
                    beat(self.name, "ok", status or "ok")
                else:
                    beat(self.name, "idle", "시간 외")
                time.sleep(self.interval)
            except KeyboardInterrupt:
                self.log("종료")
                break
            except Exception as e:
                beat(self.name, "error", str(e)[:100])
                self.log(f"에러: {e}")
                traceback.print_exc()
                time.sleep(60)

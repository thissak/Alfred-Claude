# Alf Agent Guide

## Project

Alf is a personal AI assistant that runs on macOS and talks over iMessage.
The current production direction is bridge mode plus a runtime orchestrator.

Primary runtime path:

```text
iMessage
-> src/alf_bridge.py
-> run/inbox/*.json
-> src/process_inbox.py
-> src/runtime/orchestrator.py
-> run/outbox/*.json
-> src/alf_bridge.py
-> iMessage
```

Scheduled jobs run through:

```text
src/runtime/scheduler_worker.py
-> src/runtime/orchestrator.py::handle_scheduled_job()
-> run/outbox/*.json
-> src/alf_bridge.py
```

## SSOT (Single Source of Truth)

**맥프로** = 코드 편집·git·Claude Code 사용 (유일한 SSOT)
**맥미니** = 런타임 전용 (데몬·DB·iMessage)

배포: 맥프로에서 `./deploy.sh` → rsync → 맥미니

### 맥미니에서 허용되는 작업
- `python3 daemon_ctl.py status/logs/stop/start` — 데몬 운영
- `sqlite3 data/market.db` — DB 직접 조회
- `cat run/outbox/*.json`, `tail logs/*.log` — 상태 확인
- 긴급 데몬 재시작

### 맥미니에서 금지
- **코드 편집 금지** — 다음 deploy.sh에서 덮어써짐
- **git 명령 금지** — .git 없음
- **Claude Code로 코드 수정 금지**

코드 수정이 필요하면 반드시 맥프로에서 편집 → `./deploy.sh -r` 배포.

### 문서 우선순위
- Current progress: `docs/PROGRESS.md`
- Architecture decisions: `docs/adr/`
- Temporary handoff notes: `docs/handoff/`
- Change history: `docs/CHANGELOG.md`

If a handoff doc conflicts with an ADR or current code, trust the code first, then ADR, then handoff notes.

## Working Rules

- Address the user as `감독님`.
- Keep bridge mode stable. Do not break `run/inbox` and `run/outbox` contracts.
- Keep data local unless the task explicitly needs an external service.
- Avoid destructive actions on launchd, logs, memory DB, or message DB without clear need.
- When validating messaging flows, prefer a safe path first:
  safe stubs or temporary outbox before real iMessage sends.
- If you must do a real end-to-end send, use a clearly labeled temporary schedule or test message and clean it up after.
- KIS and other brokerage credentials are read-only by policy.
- Do not add or run stock order, cancel, or modify flows.
- Stock automation may fetch balances, fills, quotes, rankings, and analysis inputs only.
- KIS access must go through `src/kis_readonly_client.py`.
- Do not call Korea Investment endpoints directly from ad hoc scripts or new modules.

## Key Files

- `src/runtime/orchestrator.py`: message and schedule orchestration
- `src/runtime/scheduler_worker.py`: due schedule worker
- `src/process_inbox.py`: inbox watcher and runtime entrypoint
- `src/alf_bridge.py`: iMessage bridge for inbox and outbox
- `src/memory.py`: SQLite memory and history
- `src/scheduler.py`: schedule storage and due-job logic
- `src/tools/`: runtime tools for memory, notes, and schedule parsing
- `daemon_ctl.py`: dev and launchd daemon management

## Daemons

Operational daemons (launchd, 8개):

- `bridge` — iMessage 브릿지
- `inbox` — 수신 메시지 처리
- `schedule` — 예약 작업 실행
- `email` — 네이버 IMAP
- `collector` — 장마감 전종목 수집
- `intraday` — 장중 급등/급락 알림
- `market-api` — DB HTTP API (port 8001)
- `buy-alert` — 매수 타이밍 알림
- `trump` — 트럼프 SNS 모니터

Useful commands:

```bash
python3 daemon_ctl.py status
python3 daemon_ctl.py logs schedule -f
python3 daemon_ctl.py install schedule
python3 daemon_ctl.py install bridge
python3 daemon_ctl.py install inbox
```

## Validation

Minimum checks for code changes that touch runtime flow:

```bash
PYTHONPYCACHEPREFIX=/tmp/alf_pycache python3 -m py_compile daemon_ctl.py src/process_inbox.py src/runtime/orchestrator.py src/runtime/scheduler_worker.py
```

For safe end-to-end checks, prefer:

- temporary inbox/outbox directories
- patched `send_imessage`
- patched GPT call

For real end-to-end checks:

- record the exact test job or message used
- verify `logs/schedule.log` or relevant daemon logs
- verify `run/outbox` drain behavior
- clean up the temporary test schedule if it is not one-shot

## Done Criteria

A runtime refactor is not done until:

- code path works through `src/runtime/`
- daemon wiring is updated if needed
- a safe validation path has been run
- `docs/PROGRESS.md` is updated when the project status changed
- any lasting architecture decision is reflected in `docs/adr/` if the design changed materially

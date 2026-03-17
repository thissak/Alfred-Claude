# Alf Overview

이 파일은 기존 Claude Code 기준 개요 문서다.

Codex 작업 규칙과 운영 기준은 이제 `AGENTS.md`를 우선 사용한다.
현재 프로젝트 상태와 다음 작업은 `docs/PROGRESS.md`를 본다.

## Summary

- 개인 iMessage AI 비서
- macOS 상주 실행
- 현재 운영 경로는 bridge + runtime orchestrator
- 레거시 `src/alf.py` / `src/brain.py`는 기본 운영 경로에서 퇴역

## Current Runtime

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

스케줄 실행 경로:

```text
src/runtime/scheduler_worker.py
-> src/runtime/orchestrator.py
-> run/outbox/*.json
-> src/alf_bridge.py
```

## Notes

- 기억: `src/memory.py`
- 스케줄: `src/scheduler.py`
- 런타임 도구: `src/tools/`
- 데몬 관리: `daemon_ctl.py`

세부 운영 규칙은 `AGENTS.md`를 기준으로 유지한다.

# Alf Overview

이 파일은 기존 Claude Code 기준 개요 문서다.

Codex 작업 규칙과 운영 기준은 이제 `AGENTS.md`를 우선 사용한다.
현재 프로젝트 상태와 다음 작업은 `docs/PROGRESS.md`를 본다.

## Summary

- 개인 iMessage AI 비서
- macOS 상주 실행
- 운영 경로: bridge + runtime orchestrator

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

## 인프라 분리

- 맥미니 = 서버 (데몬 + 수집 + iMessage), 맥프로 = 분석 워크스테이션
- 상세: `docs/infra-split.md`

## Notes

- 기억: `src/memory.py`
- 스케줄: `src/scheduler.py`
- 런타임 도구: `src/tools/`
- 데몬 관리: `daemon_ctl.py`

세부 운영 규칙은 `AGENTS.md`를 기준으로 유지한다.

## 이란전 추적

일일 업데이트 요청 시 아래 프로토콜을 따른다.

- 문서: `docs/iran-war/` (README=타임라인, analysis.md=누적분석, daily/=일별기록)
- 분석 축 5개: 군사상황, 트럼프 출구전략, 이란 에너지인질전략, 삼각교착, 경제지표
- 검색: Claude WebSearch + GPT Codex (`codex exec`) 병렬 실행, 결과 병합
- 기록: daily/{date}.md에 상황+수치+분석메모 저장, analysis.md 누적 업데이트
- 컨텍스트: 새 대화 시작 시 `docs/iran-war/analysis.md` + 최근 daily 읽어서 이어갈 것

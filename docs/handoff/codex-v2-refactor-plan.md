# Codex V2 Refactor Plan

Archived planning note.

This file is kept only as historical context for the runtime migration.
Current source of truth moved to:

- `AGENTS.md`
- `docs/PROGRESS.md`
- `docs/adr/009-codex-agent-runtime.md`

Parts of this plan are already implemented, and some file mappings below are no longer current.

## Goal
현재 브리지 기반 구조를 유지하면서, 프로젝트를 Codex 중심 개인 비서 런타임으로 단계적으로 전환한다.

## Phase 0: Interface Freeze
먼저 유지할 인터페이스를 고정한다.

- inbox JSON 형식 유지
- outbox JSON 형식 유지
- SQLite 메모리 DB 유지
- 현재 launchd/daemon 실행 방식 유지

이 단계의 목표는 외부 동작을 깨지 않고 내부 구조만 바꾸는 것이다.

## Phase 1: Orchestrator 도입

신규 파일:

- `src/runtime/orchestrator.py`
- `src/runtime/event_bus.py`
- `src/runtime/policies.py`

변경:

- `src/process_inbox.py`는 inbox 파일을 읽은 뒤 `orchestrator.handle_event()`만 호출
- 모델 직접 호출, 파일 삭제, 응답 생성 로직은 오케스트레이터 하위로 이동

완료 조건:

- 현재와 동일하게 메시지 1건 처리 가능
- 응답 생성 전 이벤트 로그가 남음

## Phase 2: Memory 분리

신규 파일:

- `src/memory/store.py`
- `src/memory/history.py`
- `src/memory/recall.py`
- `src/memory/profile.py`
- `src/memory/tasks.py`

기존 파일:

- `src/memory.py`는 호환용 facade로만 남기고 내부 호출을 신규 모듈로 위임

완료 조건:

- 최근 대화, 프로필, 관련 회상, 작업 메모리가 각자 독립 API를 가짐
- `memory.py` 단일 파일의 역할 과밀이 해소됨

## Phase 3: Tool Layer 도입

신규 파일:

- `src/tools/memory.py`
- `src/tools/schedule.py`
- `src/tools/notes.py`
- `src/tools/email.py`
- `src/tools/stocks.py`

변경:

- `[MEM:]`, `[SCHED:]`, `[NOTE:]` 파싱 의존을 점진적으로 줄임
- 오케스트레이터 또는 에이전트가 명시적 tool을 호출

완료 조건:

- 상태 변경이 문자열 프로토콜이 아니라 함수 인터페이스를 통해 발생
- 실패한 액션의 원인을 로그에서 추적 가능

## Phase 4: Services 정리

신규 파일:

- `src/services/model_router.py`
- `src/services/notifier.py`
- `src/services/scheduler.py`

변경:

- `src/brain.py`는 제거 대상
- `src/scheduler.py`는 서비스 계층으로 이동

완료 조건:

- 모델 호출과 비즈니스 로직이 분리됨
- proactive 알림 발송 경로가 notifier를 통해 단일화됨

## Phase 5: Legacy 제거

제거 대상:

- `src/alf.py`
- `src/brain.py`

사전 조건:

- bridge 경로가 메모리/일정/노트/응답 생성 전체를 대체
- launchd에서 레거시 데몬이 더 이상 필요 없음

완료 조건:

- 사용자 메시지 처리 경로가 하나로 통일됨
- 문서와 운영 방식이 신규 아키텍처 기준으로 정리됨

## File Mapping

- `src/alf_bridge.py` -> `src/channels/imessage_in.py`, `src/channels/imessage_out.py`
- `src/process_inbox.py` -> `src/runtime/orchestrator.py` 호출기
- `src/memory.py` -> `src/memory/*`
- `src/scheduler.py` -> `src/services/scheduler.py`
- `skills/research/save_note.py` -> `src/tools/notes.py` 또는 `src/services/notes_adapter.py`
- `daemons/email_daemon.py` -> `src/channels/email_in.py` 또는 `src/tools/email.py`

## Risks

- 레거시 태그 프로토콜과 신규 tool 호출이 충돌할 수 있음
- `alf.db`를 유지하면서 스키마 분리가 필요할 수 있음
- AppleScript 기반 Notes/iMessage 연동은 실패 시 재시도 정책이 필요함
- Codex 런타임을 상주시킬지, 이벤트마다 호출할지 운영 선택이 필요함

## First Implementation Slice

가장 먼저 바꿀 범위:

1. `src/runtime/orchestrator.py` 추가
2. `src/process_inbox.py`를 오케스트레이터 호출기로 축소
3. 메모리 읽기 API만 `src/memory/history.py`, `src/memory/recall.py`로 분리
4. 응답 생성은 기존 `ask_gpt()`를 그대로 사용

이렇게 하면 동작 변화 없이 구조 전환을 시작할 수 있다.

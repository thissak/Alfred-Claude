# ADR 009: Codex 중심 개인 비서 런타임으로 전환

## Status
Proposed

## Context
현재 프로젝트는 두 개의 경로가 공존한다.

- 레거시: `src/alf.py` → `src/brain.py` → `claude -p`
- 브리지: `src/alf_bridge.py` → `run/inbox/*.json` → `src/process_inbox.py`

브리지 전환으로 입출력 분리는 이미 이뤄졌지만, 아직 구조는 "메시지 1건을 받아 응답 1건을 생성"하는 처리기에 가깝다. 사용자가 원하는 시스템은 openclaw류의 개인 비서로, 다음 조건이 필요하다.

- Codex를 단순 응답 모델이 아니라 실행 런타임으로 사용
- 기억, 일정, 조사, 보고, 후속 액션을 하나의 상태 기계에서 처리
- 사용자가 말하지 않아도 먼저 알림/브리핑/리포트를 보낼 수 있음
- 도구 실행과 응답 생성을 분리하여 안정성을 높임

## Decision
프로젝트의 중심을 "채널 브리지 + 단발성 응답기"에서 "이벤트 기반 오케스트레이터 + Codex 런타임"으로 옮긴다.

새 상위 구조는 다음과 같다.

```text
channels -> event bus -> orchestrator -> agent runtime -> tools/services
                                     \-> memory service
                                     \-> notifier
```

상세 흐름:

```text
iMessage / email / scheduler
    -> channels/*
    -> event bus (normalized event)
    -> orchestrator
       - intent classify
       - memory recall
       - plan next action
    -> agent runtime
       - tool selection
       - tool execution
       - result synthesis
    -> memory write / task update
    -> notifier / channel reply
```

## Module Boundaries

### 1. channels
외부 입출력만 담당한다.

- `imessage_in`: `chat.db` 폴링, 수신 이벤트 생성
- `imessage_out`: outbox 또는 직접 발신
- `email_in`: 메일 수집 후 이벤트 생성
- 추후 `calendar_in`, `file_watch_in` 확장 가능

채널은 비즈니스 로직을 가지지 않는다.

### 2. event bus
모든 입력을 공통 이벤트 구조로 정규화한다.

예시:

```json
{
  "id": "evt_20260317_001",
  "type": "message.received",
  "channel": "imessage",
  "sender": "user",
  "text": "내일 아침에 깨워줘",
  "ts": "2026-03-17T09:00:00+09:00"
}
```

최소 역할:

- 이벤트 저장
- 중복 방지
- 재처리 가능성 보장

### 3. orchestrator
시스템의 핵심 진입점이다.

입력 이벤트를 받아 다음 중 하나로 라우팅한다.

- `reply_only`: 일반 대화 응답
- `tool_call`: 일정 생성, 노트 저장, 조회 등
- `research`: 조사 후 구조화된 결과 저장
- `proactive`: 먼저 말 걸기, 브리핑, 리포트
- `defer`: 즉시 답하지 않고 후속 작업 큐에 적재

오케스트레이터는 모델 호출 전에 항상 다음을 수행한다.

- 최근 대화 조회
- 프로필/선호 메모리 조회
- 관련 과거 대화 recall
- 현재 활성 작업/스케줄 조회

### 4. agent runtime
Codex가 사용하는 실행 계층이다.

역할:

- 계획 수립
- 도구 선택
- 실행 결과 판독
- 실패 시 재시도 또는 대체 경로 선택

원칙:

- 모델은 직접 외부 상태를 바꾸지 않는다
- 상태 변경은 등록된 tool/service를 통해서만 수행한다
- 응답 생성과 액션 실행 결과를 분리 기록한다

### 5. memory service
메모리를 다음처럼 분리한다.

- `profile_memory`: 유저 선호, 관계, 습관
- `task_memory`: 현재 진행 중인 일, 약속된 후속 행동
- `episodic_memory`: 대화/실행 로그
- `knowledge_memory`: 정리된 조사 결과, 노트
- `schedule_memory`: 리마인더, 반복 작업, 실행 이력

기존 `memory.py`의 역할은 이 서비스로 분해한다.

### 6. tools/services
명시적 인터페이스를 가진 실행 단위다.

- `notes.create`
- `schedule.create`
- `schedule.cancel`
- `memory.save`
- `memory.recall`
- `email.fetch`
- `stocks.report`
- `web.fetch`
- `files.read`
- `files.write`

프롬프트 기반 암묵적 태그(`[MEM:]`, `[SCHED:]`, `[NOTE:]`)는 점진적으로 축소한다.

### 7. notifier
사용자에게 먼저 말 거는 출력 계층이다.

- 스케줄 기반 브리핑
- 이벤트 기반 알림
- 장시간 미처리 작업에 대한 리마인드
- 보고서 발송

## Directory Plan

```text
src/
  channels/
    imessage_in.py
    imessage_out.py
    email_in.py
  runtime/
    orchestrator.py
    agent.py
    event_bus.py
    policies.py
  memory/
    store.py
    recall.py
    profile.py
    history.py
    tasks.py
  services/
    scheduler.py
    notifier.py
    model_router.py
  tools/
    notes.py
    memory.py
    schedule.py
    email.py
    stocks.py
  app.py
```

## Migration Strategy

1. 브리지 경로를 유지한 채 오케스트레이터를 도입한다.
2. `process_inbox.py`를 오케스트레이터 호출기로 축소한다.
3. 메모리/스케줄/노트 로직을 tool/service 계층으로 이동한다.
4. 레거시 `alf.py`, `brain.py` 의존을 제거한다.
5. proactive notifier를 붙여 먼저 말 거는 동작을 활성화한다.

## Consequences

장점:

- Codex를 응답기보다 실행기 역할에 맞게 사용 가능
- 기능 추가 시 프롬프트 수정이 아니라 tool 추가로 확장 가능
- proactive assistant 구현이 쉬워짐
- 실패 지점과 로그가 명확해짐

단점:

- 현재보다 파일 수와 계층 수가 늘어남
- 초기에 이벤트/도구 인터페이스를 명확히 정의해야 함
- 레거시 프로토콜과 신규 도구 방식이 한동안 공존함

## Success Criteria

- iMessage 입력이 오케스트레이터를 통해 처리된다
- 메모리 저장/조회가 명시적 tool 호출로 동작한다
- 일정/노트/이메일/주식 기능이 동일 실행 인터페이스를 공유한다
- 사용자가 말하지 않아도 브리핑/알림이 발송된다
- `src/alf.py`와 `src/brain.py`를 제거해도 기능 회귀가 없다

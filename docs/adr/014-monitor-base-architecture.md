# ADR 014: MonitorBase 통합 아키텍처

## Status
Accepted

## Context
7개 모니터링 데몬(trump, health, alert, intraday, collector, email, buy-alert)이 각각 독립적으로 구현되어 있었다. 공통 패턴(폴링 루프, heartbeat, outbox, claude -p 호출, 에러 처리)이 매번 중복되어 ~200줄의 보일러플레이트가 반복되고, 새 모니터 추가 시 처음부터 작성해야 했다.

## Decision
`src/monitor_base.py`에 `MonitorBase` 클래스를 도입하여 공통 인프라를 통합한다.

- **서브클래스가 구현**: `check()` — 1회 체크 로직 (데이터 수집 → 필터 → claude → outbox)
- **서브클래스가 설정**: `name`, `interval`, `weekday_only`, `time_gate`, `claude_model`, `claude_max_turns`, `claude_tools`, `claude_system_prompt`
- **베이스가 제공**: `run()` (데몬 루프), `ask_claude()`, `write_outbox()`, `log()`, 시간 게이트, RUN_NOW 모드, heartbeat
- **상태 관리는 일반화하지 않음** — 각 데몬의 상태 형태가 다르므로(last_id 파일, JSON, 메모리 set, Pub/Sub ACK 등) 서브클래스의 private 메서드로 유지

## Consequences
- 새 모니터 추가: Python 파일 1개(~50줄) + daemon_ctl 등록 1줄
- 기존 데몬 코드 32~51% 감소 (collector 제외, 파이프라인 로직은 유지)
- daemon_ctl.py, LaunchAgent plist 변경 없음
- YAML/플러그인 시스템 없이 순수 Python 상속으로 구현 — 의존성 최소화

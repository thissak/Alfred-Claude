# ADR 018: freshness 검사 — 보조테이블(수급/밸류/스크리닝) 커버리지 확장

## Status
Accepted (2026-05-25)

## Context
ADR-017의 freshness 검사기는 `daily_prices`의 완전성·신선도만 검증한다. 그런데
collector 파이프라인은 데이터 경로가 둘로 갈린다:

- `daily_prices`·`daily_indices` ← PyKRX (별도 백필 경로, 거의 항상 최신 유지)
- `investor_flow`·`daily_valuations`·`daily_screening` ← KIS
  (`scan_prices` → `scan_investor_flow` → `compute_screening` 체인)

5/21 일일수집이 KIS `ConnectionError`로 `scan_prices`에서 크래시 → 그 뒤 단계가
5/20에 정지했는데, `daily_prices`는 PyKRX로 5/22까지 멀쩡해서 freshness 검사기가
"정상"으로 판정 → 수급/스크리닝이 이틀 밀렸는데도 알림·복구가 없었다. ADR-017이
문서화한 한계(1: indices까지 누락된 interior, 2: ETF 특수코드)와는 다른, **인식되지
않았던 사각지대**. collector는 평일 15:45 1회만 트리거되고 누락일 자동복구가 없어
한 번의 크래시가 그대로 정체로 남았다.

## Decision
freshness 검사를 **멀티소스 신선도**로 확장한다.

- `freshness_monitor.check()`가 `investor_flow`·`daily_screening`의 최신일을 거래일
  오라클(`latest_trade` = daily_prices∪indices 최신)과 비교 → 뒤처지면 stale로 보고
  (알림 detail에 어떤 테이블이 어느 날짜에 정체인지 명시).
- 자동복구는 별도 경로 `_heal_flow` → `scripts/backfill_flow.py --since`. 기존 `_heal`
  (daily_prices = `backfill_kis_history.py`)와 데이터 경로가 다르므로 분리한다.
  collector 윈도우(15:40~17:00)·중복실행(pgrep)·`FRESHNESS_AUTOHEAL` 가드는 `_heal`과 동일.
- `backfill_flow.py`는 collector_daemon 함수를 재사용한다
  (`scan_investor_flow` + `compute_valuations --start` + 누락일별 `compute_screening`).
  멱등 — 전 테이블이 거래일 최신과 일치하면 KIS 스캔 없이 skip.

## Consequences
- KIS 경로가 PyKRX와 독립적으로 정체돼도 검사 주기(1800s) 내에 검사기가 잡아 알림 +
  자동복구한다. silent failure 재발 방지.
- 기존 daily_prices 완전성·신선도 검사와 `_heal`은 불변(회귀 없음). 보조테이블만 stale인
  경우 prices용 `_heal`은 호출하지 않는다(빈 dates로 `backfill --since` 크래시 방지).
- **한계**: 검사는 investor_flow·daily_screening의 최신일(stale)만 본다. 과거 interior
  부분누락은 daily_prices와 마찬가지로 외부 거래일 캘린더 부재로 미커버.
  `daily_valuations`는 screening의 선행 입력이라 별도 검사를 생략 — `backfill_flow`가 함께 채운다.

관련: ADR-017(freshness 검사기 원본 — daily_prices), ADR-016(병렬+재시도), ADR-014(MonitorBase).

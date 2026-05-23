# ADR 017: 데이터 무결성 — 정직한 heartbeat + freshness 독립 검사기

## Status
Accepted (2026-05-24)

## Context
collector는 heartbeat(`run/heartbeat/collector.json`)로 상태를 보고하지만,
`MonitorBase`가 `check()`가 예외 없이 끝나면 무조건 `beat("ok")`였다. 게다가
`scan_prices` 등은 종목별 실패를 삼키고(에러 카운트만), 오케스트레이터는 반환
건수를 버렸다. 결과:

- ConnectionError로 전 종목 수집이 0건이어도 `check()`는 "수집 완료"를 반환 → heartbeat "ok".
- heartbeat가 **liveness(프로세스 생존)**만 증명하고 **freshness/completeness
  (데이터가 실제 들어왔는가)**는 검증하지 못함.
- 5/13·15·21·22가 통째로/부분 누락됐는데도 알림 없이 차트가 5/20에 정체 — silent failure.

ADR-016(병렬+재시도)은 실패 *확률*을 낮추지만 ConnectionError 확률을 0으로
만들 수는 없다. 무결성에는 별도의 *보장* 장치가 필요하다.

## Decision
heartbeat를 정직하게 만들고, writer와 독립된 검증자를 둔다.

1. **정직한 heartbeat** — `MonitorBase.check()`가 `(status, detail)` 튜플 반환 시
   그 status로 beat한다(기존 str 반환 데몬은 "ok"로 비파괴 호환). collector는
   수집 0건/기대종목의 80% 미만이면 `("error", …)`를 반환.

2. **freshness 독립 검사기**(`daemons/freshness_monitor.py`) — collector 자기보고와
   무관하게 DB를 직접 읽어 검증한다.
   - 후보 거래일 = `daily_prices` 날짜 ∪ `daily_indices` 날짜. 둘 중 하나만 들어와도
     거래일로 인식 → collector가 어느 쪽을 놓쳐도 감지.
   - 완전성: 날짜별 `daily_prices` 행수 < 후보일 중앙값×0.9면 부분수집(gap).
   - 신선도: `daily_prices` 최신일 < 거래일 최신이면 stale.
   - gap/stale 발견 → 상태변화 시 1회 iMessage 알림(데드맨 스위치) +
     `backfill --since` 자동복구(수집 윈도우·중복실행 가드, ok→bad 전이 시 1회).

   오라클로 `daily_indices`만 쓰면 collector가 지수까지 같이 놓친 날(=비독립)을
   못 잡으므로 `daily_prices`와의 합집합을 쓴다.

## Consequences
- 수집이 조용히 실패해도 heartbeat가 error를 보고하고, freshness 검사기가 독립적으로
  갭/정체를 잡아 알림·자동복구한다.
- **한계 1**: `daily_prices`·`daily_indices` 둘 다 없는 interior 누락(collector 전량실패로
  지수까지 못 받은 과거 어느 날)은 외부 거래일 캘린더가 없어 못 잡는다. 단 최신일
  정체는 stale로 잡힌다.
- **한계 2**: 자동복구가 쓰는 `backfill --since`(FHKST03010100/"J")는 ETF·ETN·스팩·일부
  특수코드에 0행을 반환하고, 읽기전용 가드가 대체 일봉 API(FHKST01010400)도 차단한다.
  따라서 그 종목군의 **과거** 갭(예: 5/13·15·21·22의 잔여 ~49종목)은 복구 불가 —
  라이브 collector(inquire-price)가 당일 수집하는 것으로만 커버. 비핵심 상품군이라 영향 제한적.
- 새 launchd 데몬 `com.alf.freshness`(interval 1800s). `FRESHNESS_AUTOHEAL=0`으로
  알림만 모드 전환 가능.

관련: ADR-016(병렬+재시도, 확률 저감), ADR-014(MonitorBase).

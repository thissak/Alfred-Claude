# ADR 016: KIS 대량 수집 병렬화 — 레이트게이트 + 재시도

## Status
Accepted (2026-05-24)

## Context
전 종목(~4,400) KIS 일봉/수급 수집이 두 경로에서 문제였다.

1. **과거 백필**: daily_prices가 5년(2021~)뿐이라 더 깊게 채우려 했으나, KIS `inquire-daily-itemchartprice`(FHKST03010100)는 **콜당 ~4.6초 latency + 100행/콜**. 순차로는 ~8.8만 콜 × 4.6초 ≈ 며칠.
2. **일일 collector**: `scan_prices`/`scan_investor_flow`가 전 종목을 **순차 호출 + 재시도 없음**. 일일 수집 ~6.6시간 + `ConnectionError` 한 번에 단계 전체가 끊겨 최근 거래일이 통째로 누락(5/13·15·21·22).

실측으로 확인한 사실:
- KIS의 ~4.6초는 *latency*라 동시 요청으로 겹치면 사라진다.
- 진짜 한계는 **"초당 거래건수"(~13 RPS)**. 동시성을 높여도 이 한계를 넘으면 거부된다.
- 토큰은 파일 캐시(23h)라 발급은 하루 1회 — 병렬과 무관.

## Decision
KIS 대량 수집은 **latency-bound**로 보고, 공통 병렬 패턴을 적용한다.

- **전역 레이트게이트** — 락 + 다음 슬롯 타임스탬프로 초당 콜을 `RATE`(~11)로 제한. 동시성과 무관하게 ~13 RPS 한계 아래 유지.
- **스레드풀**(~40~50 워커) — 콜을 겹쳐 latency를 흡수. 게이트가 binding constraint.
- **재시도** — `rt_cd≠0`(초당초과 등)나 예외(ConnectionError)면 짧게 sleep 후 5~6회 재시도. 일시 실패로 누락되지 않게.
- **DB 쓰기**: 백필은 스레드 공유 커넥션(`check_same_thread=False`+락, WAL busy_timeout) + 멱등 upsert + 체크포인트 재개. collector는 워커가 fetch만 하고 결과를 모아 종료 시 일괄 upsert(동시 쓰기 없음).

적용:
- `scripts/backfill_kis_history.py` — 과거 백필(상장일/1990까지). `--pilot`/`--since` 모드.
- `daemons/collector_daemon.py` — `collect_parallel()` 헬퍼로 현재가·수급 수집 전환.

## Consequences

### 긍정
- 과거 백필: 순차 며칠 → **~2.5시간**에 30년치(daily_prices 4.01M→13.79M행).
- collector: 일일 수집 ~6.6시간 → **수십 분**. 간헐 ConnectionError를 재시도로 견뎌 **최근일 누락 재발 방지**.
- 동일 패턴(게이트+풀+재시도)을 두 경로가 공유 — 검증된 코드 재사용.

### 부정 / 트레이드오프
- 레이트게이트 튜닝값(RATE)이 KIS 한계에 의존 — 한계 변하면 조정 필요. 초과 시 재시도로 자가 보정되나 낭비 콜 발생.
- 스레드 공유 DB 쓰기는 락/WAL 의존. 단일 사용자·단일 호스트라 경합 낮음.
- 옛 KIS 일봉은 시가/고저=0(종가만) 행이 섞임 → 적재 후 종가로 플랫화 + 차트 API에서 종가≤0 제외로 보정.

## 관련
- ADR 015 (stock.goldenlabs.dev 배포) — 이 데이터를 쓰는 차트.
- ADR 014 (MonitorBase) — collector가 상속하는 데몬 베이스.

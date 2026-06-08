# ADR 019: 미국 국채금리 트래킹 — 야후 ^TNX 소스 + daily_indices 재사용

## Status
Accepted

## Context
stock.goldenlabs.dev에 미국 10년물 국채금리를 매크로 핵심 지표로 추가하기로 했다(전용 `/rates` 레퍼런스 페이지 + Alfred 일일/변동 보고). 국내 데이터는 PyKRX/KIS로 수집하지만 미국 국채금리 수집 인프라는 없었고, 데이터 소스·저장 위치·표시 방식·보고 메커니즘을 결정해야 했다.

데이터 소스 후보 (맥프로 실측):
- **FRED(DGS10)**: 미 연준 공식, 일별 확정치. 그러나 맥프로에서 read timeout.
- **stooq(10usy.b)**: CSV. 그러나 JS 봇 챌린지 페이지로 차단.
- **야후 ^TNX chart API**: OHLC + 현재값/52주 meta, urllib만으로 접근. 맥프로·맥미니 모두 동작.

## Decision
- **데이터 소스 = 야후 파이낸스 `^TNX` chart API** (`src/treasury_yield.py`, urllib+json, API키·라이브러리 0).
  - 백필은 `period1=0&period2=<now>&interval=1d`로 일봉 전체(14,129행, 1970~). `range=max`는 야후가 월봉으로 다운샘플(159건)하는 함정이라 period 방식 사용.
  - `meta.regularMarketPrice`가 미 장중 실시간(~15분 지연)이라 변동 알림에 활용.
  - 전일대비는 `meta.chartPreviousClose`(차트 범위 시작 직전, 부정확) 대신 일봉 직전 거래일 종가로 계산.
- **저장 = 기존 `daily_indices` 재사용** (code='US10Y', close=yield REAL). 단일 지표에 전용 테이블·범용 매크로 테이블은 과한 추상화라 배제.
- **표시 = 종목 검색과 분리된 전용 `/rates` 페이지**. `server.py`에 `/api/rates`만 추가, 기존 종목 검색/차트 경로는 비오염.
- **보고 = MonitorBase 상속 단일 데몬**(`daemons/treasury_monitor.py`). 매일 KST 07:30 아침 루틴 + 장중 기준가 대비 ±8bp 변동을 한 데몬에서 처리, 중복방지 상태는 `run/treasury_state.json`(base_price 기준 8bp마다 재알림). 신규 폴링·재시도 primitive는 손코딩하지 않고 MonitorBase(ADR 014) 재사용.

## Consequences
- (+) 외부 의존성 0(urllib), API 키 불필요, 맥프로/맥미니 동일 동작.
- (+) `daily_indices` 재사용으로 freshness 검사 비간섭(검사기는 code='0001' KOSPI만 거래일 오라클로 사용 — ADR 017/018).
- (+) 단일 소스로 백필·일일보고·장중 실시간 모두 커버.
- (−) 야후 비공식 API라 포맷 변경 리스크 → 방어적 파싱(None 폴백, 데몬 지속). 장기 불안정 시 FRED 키 발급 경로로 전환 여지.
- (−) 52주 레인지가 페이지(DB 종가 252거래일)와 모니터(야후 meta, 장중 포함)에서 소수점 미세차 — 의도적 분리(페이지=종가차트 정합, 모니터=실시간 컨텍스트).
- (−) 미 국채금리는 KST와 거래일 캘린더가 달라 `daily_indices`에 미국 거래일로 혼재되나 code 구분으로 무해.
- (−) 맥미니 collector_daemon과 별개로 모니터 폴링이 daily_indices를 갱신 → 모니터 정지 시 페이지 데이터도 정체(freshness 검사 대상 추가는 추후 검토). 상세 [[docs/handoff/treasury-rates-handoff.md]]

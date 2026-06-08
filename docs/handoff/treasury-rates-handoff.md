# 미국 10년물 국채금리 — Handoff

작성: 2026-06-09 · 상태: 맥프로 코드+백필+검증 완료, 맥미니 배포 대기

## 현재 상태

stock.goldenlabs.dev에 미국 10년물 국채금리(US10Y) 트래킹을 추가했다.

- **레퍼런스 페이지** `/rates` — 종목 검색과 분리된 독립 페이지. 골드 area 라인차트 + 현재값/전일대비(bp)/52주 레인지. `index`/`notes` 헤더에 `[🇺🇸 국채]` 링크.
- **데이터 소스** 야후 `^TNX` (`src/treasury_yield.py`, urllib+json). 키·라이브러리 불필요. `daily_indices` code='US10Y' 재사용(close=yield, REAL).
- **백필** `scripts/backfill_us10y.py` — 맥프로 로컬 `data/market.db`에 14,129 일봉(1970~2026) 완료.
- **모니터** `daemons/treasury_monitor.py` — 매일 KST 07:30 아침 보고 + 장중 ±8bp 변동 알림. `daemon_ctl` `treasury` 등록.

검증 7/7 PASS (`.claude-criteria.md`).

## 다음 작업 — 맥미니 배포 (별도 승인 필요)

맥미니는 `MARKET_DB_HOST` 원격 모드라 맥프로 로컬 백필이 반영 안 됨. 배포 시:

1. **rsync 동기화** — `src/treasury_yield.py`, `scripts/backfill_us10y.py`, `daemons/treasury_monitor.py`, `apps/stock-chart/{server.py,web/rates.html,web/index.html,web/notes.html}`, `daemon_ctl.py` (라이브 `~/Projects/Alfred-Claude`는 git 아님 → rsync)
2. **맥미니에서 백필** — `python3 scripts/backfill_us10y.py` (맥미니 `data/market.db`에 US10Y 적재). 맥미니 네트워크에서 야후 접근 가능 여부 먼저 확인.
3. **데몬 등록** — `python3 daemon_ctl.py start treasury` (launchd `com.alf.treasury`). `ALF_MY_NUMBER` 설정돼 있어야 실발신.
4. **stock-chart 재시작** — `/rates` 라우팅 반영 위해 `daemon_ctl restart stock-chart`.

## 알려진 이슈 / 설계 메모

- **52주 레인지 소스 차이(의도적)**: 페이지(`get_rates`)는 DB 종가 252거래일 max/min, 모니터(`fetch_quote`)는 야후 `meta.fiftyTwoWeekHigh/Low`(장중 포함). 소수점 미세차 발생 — 페이지는 차트(종가 라인)와 정합, 모니터는 실시간 컨텍스트라 분리 유지.
- **아침 보고 매일(주말 포함)**: 미 채권시장 주말 휴장이라 토·일엔 금요일 종가가 그대로 발송. 평일만 원하면 `treasury_monitor.py`의 `weekday_only = True` 한 줄.
- **야후 비공식 API**: 포맷 변경 가능성 → `_result`/`_series` 방어적 파싱, 실패 시 `None`(데몬 지속). 장기적으로 불안정하면 FRED API 키 발급 경로 검토.
- **자동 수집 미통합**: 현재 모니터 폴링이 daily_indices를 갱신하지만, collector_daemon과는 별개. 모니터가 죽으면 페이지 데이터도 정체 → freshness 검사 대상 추가는 추후 검토(현재 freshness는 code='0001' KOSPI만 오라클).

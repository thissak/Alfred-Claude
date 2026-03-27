# ADR 011: 시장 데이터 SQLite DB + 수집 데몬 아키텍처

## Status
Accepted

## Context
주식 스크리너 v2에서 실시간 API 호출로 전종목 스크리닝하면 속도·호출 한도 문제가 발생한다. 장 마감 후 데이터를 일괄 수집해서 로컬 DB에 저장하면 스크리닝·분석을 오프라인으로 즉시 실행할 수 있다.

## Decision
- `src/market_db.py`: SQLite WAL 모드로 시장 데이터 전용 DB 구축 (7개 테이블: securities, daily_prices, daily_valuations, investor_flow, financials, daily_screening, journal_trades)
- `daemons/collector_daemon.py`: 장 마감 후 자동 수집 데몬 (15:45~16:20 순차 실행, 15 RPS 쓰로틀)
- `scripts/backfill_*.py`: 과거 데이터 일괄 적재용 스크립트 (OHLCV, 재무제표, 스크리닝)
- 기존 메모리 SQLite(ADR 005)와 별도 DB 파일(`data/market.db`)로 분리

## Consequences
- KIS API 호출 횟수 대폭 감소 (일 1회 수집 후 로컬 조회)
- 시계열 분석, 백테스트, 커스텀 스크리닝 가능
- DB 파일 크기 증가 (전종목 수년치 데이터)
- DART API 키 추가 필요 (재무제표 백필용)

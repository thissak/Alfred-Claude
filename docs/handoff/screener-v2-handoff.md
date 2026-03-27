# 주식 스크리너 v2 Handoff

## 완료된 작업

- KIS API 6개 엔드포인트 실제 호출 검증 (응답 필드 구조 확인)
- 통합 스키마 21개 필드 설계 (KR/US 동일 키셋)
- 정규화 모듈 (`skills/stock/screener_v2/normalize.py`)
  - `normalize_kr_from_inquire_price()` — 국내 현재가 API → 통합 스키마
  - `normalize_kr_from_ranking()` — 시가총액순위 API → 기본 정보만
  - `enrich_kr_with_inquire_price()` — ranking 결과에 PER/PBR/외인 보강
  - `normalize_us_from_search()` — 해외 조건검색 API → 통합 스키마
  - `enrich_us_with_detail()` — price-detail로 PBR/52주/업종 보강
- 필터 엔진 (`skills/stock/screener_v2/filters.py`)
  - Filter 클래스 (>=, <=, >, <, ==, !=, between)
  - apply_filters (AND 조합 + 정렬 + 제한)
  - 프리셋 5종: 저평가, 모멘텀, 수급, 대형주, 성장
- API 호출 모듈 (`skills/stock/screener_v2/kis_endpoints.py`)
  - fetch_kr_market_cap_page() — 시총순위 페이징
  - fetch_kr_price_detail() — 개별 종목 상세
  - fetch_kr_investor() + sum_investor_days() — 수급
  - fetch_us_search() — US 조건검색 (Finviz 대체)
  - fetch_us_price_detail() — US 종목 상세
- KIS readonly client에 신규 엔드포인트 5개 allowlist 추가 완료
- 단위 테스트 41개 전부 통과
- 실제 API 응답 저장: `data/kis_api_fields.json`

## 다음 작업

1. **배치 수집 스크립트** (`screener_v2/run.py`)
   - KR: market-cap 순위 페이징 → 상위 N종목 inquire-price 보강 → 필터 적용
   - US: inquire-search로 조건검색 → price-detail 보강 → 필터 적용
   - 결과를 `data/screener.json`에 저장
2. **cron 스케줄 등록**
   - KR: 16:00 KST (장 마감 후)
   - US: 06:00 KST (미장 마감 후)
3. **출력 연동**
   - Vercel 대시보드 배포 (기존 stock-report 레포 활용)
   - Alf 연동: "저PER 외인순매수 종목 알려줘" 같은 자연어 질의

## 알려진 이슈

- **해외 조건검색 valx 파라미터 9자리 제한** — `CO_EN_VALX`에 13자리 입력 시 오류. 시가총액 단위가 불명확 (달러 기준 추정, 실측 필요)
- **시가총액순위 API에 PER/PBR 없음** — 종목 코드만 확보 후 inquire-price로 보강 필요 (API 호출 2배)
- **투자자매매동향 장 시간 외 빈 값** — 장 마감 후에만 유효한 데이터 반환 확인됨
- **시가총액순위 페이징 방식 미검증** — 첫 페이지(30건)만 테스트, 연속조회 키 방식 추가 확인 필요

## 핵심 결정 사항

- SMA/RSI/MACD 등 기술적 지표 자체 계산 안 함 — KIS API가 제공하는 데이터(PER/PBR/시총/외인지분/52주 등)만 조합
- 국내는 inquire-price 하나가 밸류에이션+수급+업종 모두 커버 (핵심 API)
- 해외는 inquire-search가 Finviz 유사 조건검색 기능 제공 (핵심 API)
- indicators.py 모듈 삭제 — 불필요한 계산 로직 제거

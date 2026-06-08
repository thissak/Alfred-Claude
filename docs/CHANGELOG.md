# Alf — Changelog

## 2026-06-09

- [feat] 미국 10년물 국채금리 레퍼런스 페이지(`/rates`) — stock.goldenlabs.dev에 국채 전용 독립 페이지 추가(종목 검색 경로와 분리). 골드 area 라인차트 + 현재값/전일대비(bp)/52주 레인지 바 + 일/주/월·1Y/3Y/5Y/10Y/전체. `server.py`에 `/api/rates`·`/rates` 라우팅, `index`/`notes` 헤더에 국채 링크. `daily_indices` code='US10Y' 재사용(close=yield, REAL이라 소수 OK) — 전용 테이블 미생성 (ADR 019)
- [feat] 미국 국채금리 데이터 소스(`src/treasury_yield.py`) — 야후 `^TNX` chart API(urllib+json, API키·라이브러리 0). `fetch_history`(period1/period2 일봉 1970~ 14129행)·`fetch_quote`(현재값/전일대비/52주, 장중 실시간 ~15분 지연). FRED·stooq는 맥프로에서 timeout/봇차단으로 탈락. ⚠️ `range=max`는 월봉 다운샘플(159건) 함정 → period 방식 필수. 전일대비는 일봉 직전종가로 계산(meta.chartPreviousClose는 범위 시작 직전이라 부정확)
- [feat] `scripts/backfill_us10y.py` — ^TNX 일봉 전체 → `daily_indices`(US10Y) 멱등 백필. 맥프로 로컬 14129행(1970-01-02~) 완료
- [feat] Alfred 국채 모니터(`daemons/treasury_monitor.py`, MonitorBase) — 매일 KST 07:30 아침 루틴 보고 + 장중 기준가 대비 ±8bp 변동 알림. 폴링(15분)마다 daily_indices 갱신 → 페이지 최신화. 상태 `run/treasury_state.json`(아침보고 시 base_price=전일종가 리셋, 이후 8bp마다 재알림·스팸방지). `daemon_ctl` `treasury` 등록. 맥프로 코드+백필+검증(7/7 PASS) 완료, **맥미니 배포·실발신은 별도 승인 예정**

## 2026-05-25

- [fix] freshness 검사 사각지대 보강 — 검사기가 `daily_prices`(PyKRX 경로, 항상 최신)만 봐서 KIS 경로인 `investor_flow`/`daily_valuations`/`daily_screening`이 따로 정체돼도(5/21 ConnectionError로 5/20 정지) "정상" 판정하던 silent failure 해소. `freshness_monitor`가 보조테이블 최신일도 거래일 오라클과 비교해 stale 탐지 + `backfill_flow.py` 자동복구. `_heal_flow`는 collector 윈도우·중복·`FRESHNESS_AUTOHEAL` 가드를 기존 `_heal`과 동일하게 적용 (ADR 018)
- [feat] `scripts/backfill_flow.py` — 수급/밸류/스크리닝 백필을 collector_daemon 함수 재사용으로 래핑(`scan_investor_flow`→`compute_valuations --start`→누락일 `compute_screening`). 자동 누락일 탐지 + 전 테이블 최신이면 KIS 스캔 없이 skip(멱등). freshness 자동복구·수동 백필 공용
- [feat] stock-chart 후보 정리 페이지(`/notes`) — 논의 종목 29개를 티어/테마별(핵심·로봇우주·반도체·바이오·연금최고비중·회피·엔터)로 정리, 각 종목 → `/?code=`로 차트 링크. 국민연금%·코스닥150 편입/편출·수급추세·촉매 메모 포함. `index.html`이 `?code=` 파라미터로 종목 선택 + 헤더 양방향 링크(차트↔후보). 사이드바 관심그룹에도 동일 7그룹 추가
- [perf] stock-chart 차트 범위별 다운샘플 — 기본 로딩(전체)이 일봉 9천여봉(952KB)을 통째로 받아 느리던 것 해소. 범위에 따라 일봉(≤1Y)→주봉(3Y)→월봉(전체)으로 서버 집계(`_aggregate`/`RANGE_TF`), 전체 952KB→45KB(21배↓). 응답에 `tf` 필드 + 헤더에 현재 봉(일/주/월) 표시
- [feat] stock-chart 봉 선택(일/주/월) — 헤더에 [일]·[주]·[월] 버튼(범위와 독립). 누르면 그 봉으로 재집계 표시, 범위 버튼은 범위 기본봉(≤1Y 일·3Y 주·전체 월). 서버 `/api/ohlcv`에 `tf` 파라미터 추가. 네이버 증권 차트식 명시 전환 — 줌 자동전환(TradingView식)은 레퍼런스와 동작이 달라 미채택

## 2026-05-24

- [feat] 데이터 무결성 레이어 — heartbeat가 '프로세스 생존'만 보고 실제 데이터 유입은 검증 못 해, collector 전량실패에도 'ok'였던 silent failure 해소. `daemons/freshness_monitor.py` 신규(`com.alf.freshness`) — `daily_prices`∪`daily_indices`로 거래일 완전성·신선도를 collector와 독립 검증, gap/stale 시 iMessage 알림 + `backfill --since` 자동복구 (ADR 017)
- [refactor] 정직한 heartbeat — `MonitorBase.check()`가 `(status, detail)` 튜플 반환 지원(기존 str 데몬 비파괴 호환), collector는 수집 0건/기대종목 80% 미만이면 heartbeat `error` (ADR 017)
- [feat] KIS 일봉 과거 백필 (`scripts/backfill_kis_history.py`) — FHKST03010100 수정주가, 100행/콜 페이지네이션으로 daily_prices를 **상장일/최대 1990년까지** 확장 (4.01M→13.79M행, ~30년). KIS 콜은 latency(~4.6초)라 **스레드풀+전역 레이트게이트(~11 RPS)+재시도로 병렬화** → 순차 며칠 → ~2.5h. 멱등 upsert + 체크포인트 재개. `--since`로 최근 갭 보충 (ADR 016)
- [perf] collector 병렬화 + 재시도 — `scan_prices`/`scan_investor_flow`를 `collect_parallel`(스레드풀+레이트게이트+5회 재시도)로 전환. ConnectionError 한 번에 그날 수집이 통째로 끊겨 최근 거래일(5/13·15·21·22) 누락되던 문제 해결. 일일 수집 ~6.6시간 순차 → 수십 분 (ADR 016)
- [fix] 차트 API 결손행 처리 — 옛 KIS 데이터의 시가/고저=0(종가만 존재) 행을 종가로 플랫화(DB 69k행 정정) + 종가≤0 행은 API에서 제외해 캔들 깨짐 방지

## 2026-05-23

- [feat] stock-chart 주식 차트 웹 (`apps/stock-chart/`) — stdlib http.server + Lightweight Charts v5. 단일종목 캔들 + 거래량(별도 패널) + 이평선 5/20/60/120 + 호버 OHLCV 레전드 + 크로스헤어 날짜. `src/market_db.py` 재사용으로 `/api/ohlcv`·`/api/search` 2개 엔드포인트만 노출 (market-api 임의 SELECT는 비노출). 네이버 증권 차트 레이아웃 모사
- [feat] `daemon_ctl.py`에 stock-chart 데몬 등록 (port 8002, 맥미니 로컬 market.db 직접 조회)
- [infra] `stock.goldenlabs.dev` 비공개 배포 — 기존 `vw-stylelab` cloudflared 터널에 ingress 1줄 + CF DNS proxied CNAME + Cloudflare Access(OTP, thissak@gmail.com만, 365일). 맥미니 올인원(A안), 새 인프라 0. Access→DNS 순서로 공개 노출 0 보장. notes(goldenLabs ADR 001) 패턴 복제 (ADR 015)
- [feat] stock-chart 관심그룹 즐겨찾기 — 좌측 사이드바(그룹별 종목+시세, 클릭→차트, ★추가/+그룹/삭제). 서버 저장(`data/watchgroups.json`, `/api/groups` GET[시세포함]/PUT)로 다기기 동기화. `watchlist.yaml` 카테고리에서 초기 시드
- [feat] stock-chart 기본 차트 범위 1Y → 전체(보유 전 기간). flexbox+autoSize로 시간축이 창 크기 무관 하단 항상 노출(잘림 해결)
- [fix] stock-chart 코드리뷰 반영 — 조용한 실패 제거: 시드 예외 stderr 로깅, do_GET/PUT `traceback.print_exc()`, PUT `groups` 키 가드(빈 본문이 전체 삭제하던 footgun 차단), 프론트 저장 실패 alert

## 2026-04-09

- [refactor] MonitorBase 통합 아키텍처 (`src/monitor_base.py`) — 7개 모니터링 데몬의 공통 보일러플레이트(daemon loop, heartbeat, outbox, claude -p 호출, 에러 처리, 시간 게이트)를 베이스 클래스로 추출. 서브클래스는 `check()` 하나만 구현. 새 모니터 추가 시 파일 1개 + daemon_ctl 등록 1줄로 확장 가능 (ADR 014)
- [feat] `daemons/trump_monitor.py` — 키워드 통과 건을 `claude -p`(sonnet)로 이란전 중요도 판단 후 `important=true`일 때만 해설 포함 iMessage 발송. 단순 키워드 매칭은 관세·국내정치 노이즈까지 포워딩되던 문제를 LLM 2차 필터로 해결. 호출 실패는 로그만 남기고 해당 entry 스킵 (fallback 발송 없음). 메시지 포맷 `[Trump|긴급/주의/참고] 이란전` + 해설 + 원문 + 링크
- [fix] `skills/report/report_manager.py` 타임아웃·주말 처리 — CLAUDE_TIMEOUT 300→420초, 주말(토/일) 스킵, 타임아웃 이후라도 리포트 파일이 생성됐으면 노션 저장 복구
- [fix] `skills/report/daily_surge_manager.py` 날짜 불일치 버그 — MAX(date) 폴백으로 전일 파일을 당일 리포트로 저장하던 문제. `run_screener(today)`에 명시적 날짜 주입 + JSON date 필드 검증 + NOTION_TIMEOUT 90→180초
- [chore] `skills/report/system.md` — 리포트 파일 저장 후 즉시 종료 지시 추가 (추가 검증·웹 검색 금지)
- [feat] KIS token 발급 감사 로깅 (`src/kis_readonly_client.py`) — `_get_token()`이 신규 발급할 때마다 시각·reason·host·pid·argv·parent cmd·call stack을 `logs/kis_token.log`에 append. 정체불명의 토큰 발급 주체 추적용. 11:20 미확인 발급 이벤트 조사 중 도입
- [fix] inbox 프로세서 무응답 버그 — `_load_feeds()`가 `data/screener_rl_backtest.json`(list 타입)에서 `AttributeError`로 크래시, 전체 응답 파이프라인이 죽어 iMessage 무응답. `isinstance(feed, dict)` 가드 추가로 비정상 스키마 피드는 스킵
- [fix] `handle_event()` `mark_done()` 호출 시점을 `write_response` 뒤로 이동 — 예외 발생 시 inbox 파일이 사라지던 at-most-once 안티패턴 제거, 처리 성공 시에만 삭제
- [fix] `process_inbox.py`에 `quarantine()` 추가 — 처리 실패 메시지를 `run/inbox/failed/`로 격리해 무한 재시도 방지 + `traceback.print_exc()`로 진단성 개선

## 2026-04-08

- [feat] GCP Alert 모니터 데몬 (`daemons/alert_monitor.py`) — Pub/Sub Pull로 GCP Alert 메시지 수신 → claude -p 분석 → iMessage 알림. health-monitor-reader 서비스 계정 재사용
- [chore] `daemon_ctl.py`에 "alert" 데몬 등록 (health 데몬과 나란히)
- [docs] `docs/health-monitor.md` — GCP 헬스 모니터 구조·엔드포인트·운영 가이드 정리

## 2026-04-05

- [feat] GCP 헬스 모니터 데몬 (`daemons/health_monitor.py`) — 5분 간격 4개 엔드포인트 헬스체크 + gcloud 진단 + claude -p 분석 + iMessage 알림
- [infra] GCP read-only 서비스 계정 생성 (health-monitor-reader@etaxbook-web.iam.gserviceaccount.com) — 키 파일 `config/health-monitor-key.json`
- [chore] `daemon_ctl.py`에 "health" 데몬 등록 + 맥미니 launchd 배포

## 2026-03-29

- [feat] 예측 피드백 루프 구현 (`src/predictor.py`, `src/validator.py`) — 4대축 스코어링 + 5일 후 자동 검증 + 가중치 자동 조정
- [feat] Track A(테마 모멘텀) + Track B(눌림 가치) 이중 트랙 예측 시스템
- [feat] predictor v4 — 거래량 선행 시그널 감점, 밸류트랩(저PER+이익감소) 감점, 최소 거래량 필터(10만주)
- [feat] news 테이블 신설 + collector 뉴스 수집 — 관심종목+급등종목 뉴스 자동 수집, 맥프로에서 원격 조회
- [feat] market-api WITH/PRAGMA 쿼리 허용 — CTE 기반 복합 분석 가능
- [feat] securities 섹터 백필 — KIS inquire-price API로 3,583종목 업종 입력
- [feat] market-api 데몬 신설 (`daemons/market_api.py`) — market.db 읽기 전용 HTTP SQL 프록시 (port 8001)
- [feat] `src/market_db.py` 원격 모드 추가 — `MARKET_DB_HOST` 환경변수로 맥프로에서 맥미니 DB 원격 조회
- [feat] `daemon_ctl.py`에 market-api 데몬 등록
- [docs] 인프라 분리 문서 업데이트 — rsync → Market API 방식으로 전환

## 2026-03-28

- [feat] surge 스킬 신설 (`.claude/skills/surge/`) — 종목 일봉 이상패턴 자동 탐지 + 뉴스·수급 매칭 + 캔들차트 생성 + 노션 자동 저장
- [feat] `scripts/stock_surge_analysis.py` — 일봉 패턴 탐지(급등/급락/거래량/갭/장대봉/꼬리봉) + KIS 뉴스·투자자 API 연동
- [feat] `scripts/stock_surge_chart.py` — mplfinance 캔들차트 + 이상패턴 마킹 + 주석 자동 생성
- [feat] KIS 뉴스 API 화이트리스트 추가 (FHKST01011800, news-title)
- [docs] 이란전 Day 29 업데이트 — 후티 첫 참전, 트럼프 데드라인 4/6 재연장, 걸프 민간인프라 피격
- [docs] 이란전 analysis.md 대규모 업데이트 — 삼각→사각 교착, 시나리오 확률 재조정, 경제지표 추가
- [feat] daily_indices 테이블 신설 + 데몬 통합 — KOSPI/KOSDAQ/KOSPI200 지수 자동 수집
- [feat] 지수 5년 백필 (`scripts/backfill_indices.py`) — 네이버 금융 API 기반 3,618건
- [feat] KIS 재무 API 6개 화이트리스트 추가 — 대차대조표/재무비율/수익성/안정성/성장성/기타주요비율
- [feat] KIS 재무제표 백필 (`scripts/backfill_financials_kis.py`) — 손익+재무비율(EPS/BPS/ROE) 전종목 11.3만건
- [feat] PER/PBR 역산 (`scripts/compute_valuations.py`) — EPS+종가로 daily_valuations 5년 274만건 생성
- [feat] financials 테이블 확장 — 대차대조표(자산/부채/자본), 안정성(부채비율/유동비율), 성장성(매출/영업익 증가율), 기타(EBITDA/EV·EBITDA/배당성향) 10개 컬럼 추가
- [feat] daily_short_selling 테이블 신설 + 공매도 백필 (`scripts/backfill_extra.py`) — 1년치 종목별 공매도 체결량/비중
- [feat] 공매도 API 화이트리스트 추가 (FHPST04830000, daily-short-sale)
- [docs] KIS API 전체 카탈로그 (`docs/kis-api-endpoints.md`) — 352개 엔드포인트 조사 정리
- [chore] PyKRX 펀더멘탈 API 장애 발견 — KIS API 직접 백필로 우회

## 2026-03-27

- [feat] 시장 데이터 DB 신설 (`src/market_db.py`) — SQLite WAL 모드, securities/daily_prices/daily_valuations/investor_flow/financials/daily_screening/journal_trades 7개 테이블
- [feat] 수집 데몬 (`daemons/collector_daemon.py`) — 장 마감 후 전종목 현재가·수급·스크리닝 자동 수집, 15 RPS 쓰로틀
- [feat] 백필 스크립트 3종 — DART 재무제표(`scripts/backfill_financials.py`), PyKRX OHLCV(`scripts/backfill_ohlcv.py`), 스크리닝 지표(`scripts/compute_screening.py`)
- [chore] daemon_ctl에 collector 데몬 등록 + apps/com.alf.collector.app 번들 추가
- [feat] Trading Journal 웹앱 초기 구축 (`apps/trading-journal/`) — Next.js 16 + better-sqlite3 + Recharts, market.db 연동 대시보드
- [feat] 주식 스크리너 v2 설계 — KIS API 실제 응답 기반 TDD 구축 (`skills/stock/screener_v2/`)
- [feat] KIS API 신규 엔드포인트 5개 allowlist 추가 — 시가총액순위, 해외조건검색, 기간별시세, 투자자매매동향, 해외현재가상세
- [feat] 통합 스키마 정규화 모듈 — KR(inquire-price) / US(inquire-search, price-detail) API 응답을 21개 필드 통합 스키마로 변환
- [feat] 필터 엔진 — 다중 조건 AND 조합 + 정렬/제한 + 프리셋 5종 (저평가/모멘텀/수급/대형주/성장)
- [test] 실제 API 호출 검증 — 6개 엔드포인트 필드 구조 확인, valx 9자리 제한 등 제약사항 발견
- [test] 단위 테스트 41개 작성 (normalize 21 + filters 20)

## 2026-03-24

- [fix] inbox 프로세서 중복 실행 방지 — `fcntl.flock` 기반 단일 인스턴스 잠금 추가 (`src/process_inbox.py`)
- [refactor] 장 마감 리포트 프롬프트 구조 개선 — `-p` 하드코딩에서 `--system-prompt-file` + `watchlist.yaml` 분리 구조로 전환
- [feat] `skills/report/watchlist.yaml` — 카테고리별 관심종목 + 분석 지시 설정 파일 신설
- [feat] `skills/report/system.md` — 리포트 에이전트 시스템 프롬프트 분리

## 2026-03-23

- [feat] 이란전 일일 추적 시스템 구축 — Claude WebSearch + GPT Codex 병렬 검색, 5개 분석 축 병합 리포트
- [feat] `skills/iran-update/` 스킬 생성 — /iran-update 로 실행, save 옵션으로 파일 저장
- [docs] `docs/iran-war/daily/2026-03-23.md` — Day 24 기록 + 인프라 MAD 심층 분석
- [docs] `docs/iran-war/analysis.md` — 블러핑 구조, 시간 비대칭, 인프라 MAD, 헤게모니 5대 기둥 분석 추가
- [docs] `docs/iran-war/README.md` — 타임라인 03-23 추가
- [config] `CLAUDE.md` — 이란전 추적 프로토콜 섹션 추가

## 2026-03-19

- [refactor] 메모리 시스템 대폭 단순화 — QMD 시맨틱 검색 + FTS5 제거, 1M 컨텍스트 활용 전체 로드 방식으로 전환 (ADR 010)
- [feat] 히스토리 compaction — 500건 초과 시 오래된 대화를 Claude haiku로 날짜별 요약 압축, episode 타입 메모리로 저장
- [feat] 시스템 프롬프트에 현재 날짜/시간 주입 — 오늘/어제 데이터 구분 불가 문제 해결
- [feat] orchestrator allowedTools에 WebSearch 추가 — Alf 실시간 웹 검색 가능

## 2026-03-18

- [refactor] `AGENTS.md` 도입 — Codex 작업 규칙, runtime 운영 기준, 문서 우선순위 정리
- [refactor] `CLAUDE.md` 축소 — 개요 문서로만 유지하고 운영 규칙은 `AGENTS.md`로 이동
- [chore] handoff 문서 정리 — 오래된 POC/계정 세팅 handoff 제거, `codex-v2-refactor-plan`은 archived note로 전환
- [feat] `src/runtime/scheduler_worker.py` import 부트스트랩 보강 — launchd 앱 번들 실행 시 `src` import 경로 문제 해결
- [feat] `daemon_ctl.py` 운영 집합 정리 — `alf`를 기본 운영 데몬에서 제외하고 legacy로 분리
- [test] runtime 스케줄 실제 E2E 검증 — `schedule` 워커가 GPT 응답 생성 후 bridge를 통해 실제 iMessage 발신 확인
- [feat] `src/kis_readonly_client.py` 추가 — KIS 조회 전용 공용 client, 허용 endpoint/TR ID allowlist 적용
- [refactor] `skills/stock/fetch_stock.py`, `skills/stock/screener.py` — KIS 직접 호출 제거, readonly client 경유로 통일
- [test] KIS readonly 실조회 검증 — 지수, 국내 잔고, 당일 체결, 미국 잔고 조회 성공
- [chore] KIS 환경변수 분리 — `KIS_READONLY_APP_KEY`, `KIS_READONLY_APP_SECRET`, `KIS_READONLY_ACCOUNT`

## 2026-03-17

- [feat] GPT Codex OAuth 연동 — ChatGPT 구독 + Codex OAuth 토큰으로 GPT-5.4 호출, API 비용 없이 LLM 사용 가능
- [feat] `process_inbox.py` GPT 자동 처리 — inbox 폴링 → GPT-5.4 호출 → outbox 응답 작성, `--watch` 모드 지원
- [feat] `scripts/start-alf-agent.sh` — tmux + Claude Code + /loop 으로 inbox 자동 감시 스크립트
- [refactor] CLAUDE.md 아키텍처 업데이트 — brain.py/alf.py 레거시화, Claude Code 풀 에이전트 + bridge 모드 반영
- [feat] QMD 시맨틱 검색 연동 — `memory.py`에 `recall()`, `qmd_init()` 추가, 대화/기억 저장 시 마크다운 자동 동기화 (`data/qmd/`)
- [feat] `brain.py` 프롬프트에 `## 관련 과거 대화` 섹션 추가 — QMD BM25 검색으로 현재 메시지와 관련된 과거 대화를 시스템 프롬프트에 주입
- [feat] `alf.py` 파이프라인에 `memory.recall()` 단계 추가 — 메시지 처리 시 QMD 검색 (0.17초, Claude 호출 대비 무시 가능)
- [feat] `skills/stock/` — 주식 리포트 스킬 (한투 API 연동, 시황/포트폴리오/급등주/외인기관 매매 리포트)
- [feat] `alf_bridge.py` — iMessage ↔ inbox/outbox 파일 기반 브릿지. alf.py(레거시)의 `claude -p` 의존을 제거하고, Claude Code 풀 에이전트가 처리하는 구조로 전환
- [feat] `process_inbox.py` — inbox 메시지 읽기/outbox 응답 쓰기 헬퍼
- [feat] `skills/report/` — 장 마감 리포트 스킬. Claude Code가 한투 API 데이터 분석 → Apple Notes 저장. launchd로 매일 16:00 자동 실행
- [fix] `save_note.py` Apple Notes 폴더명 오타 "Afred" → "Alfred"
- [refactor] `brain.py` `_load_feeds()` 범용화 — items 키 없는 JSON(stock.json 등)도 10KB 이하면 프롬프트에 주입
- [chore] `daemon_ctl.py` bridge 데몬 등록, alf를 레거시로 표기
- [chore] launchd plist 추가 — `com.alf.bridge` (iMessage 브릿지), `com.alf.report` (장 마감 리포트 16:00)

## 2026-03-04

- [feat] `memory.py` SQLite 전환 — 플랫파일(.md) → SQLite(alf.db), 선택적 로딩(about:전체, calendar:+-7일, notes:30일), 키워드 검색, 레거시 자동 마이그레이션
- [feat] `scheduler.py` 내장 스케줄러 — at(1회)/daily(매일)/every(반복) 잡 관리, [SCHED:] 프로토콜로 Claude가 직접 스케줄 등록
- [feat] `brain.py` 세션 컨텍스트 강화 — 최근 대화 5건 + 활성 스케줄 목록을 시스템 프롬프트에 주입
- [feat] `alf.py` 스케줄러 통합 — 폴링 루프에서 만기 잡 체크 → Claude 호출 → 선제 발신
- [feat] `skills/scheduler/` — 스케줄러 스킬 추가 ([SCHED:] 프로토콜 가이드)
- [refactor] `alf.py` 메시지 처리 파이프라인 함수 분리 (handle_message, process_response, handle_scheduled_jobs)
- [perf] 프로파일링 계측 추가 — alf.py/brain.py에 단계별 소요시간 측정 (timed 컨텍스트매니저)

## 2026-03-03

- [feat] `daemon_ctl.py` — Swift 네이티브 .app 빌드 + launchd 데몬 관리 시스템 구현
- [fix] FDA(전체 디스크 접근) 해결 — 셸 스크립트 .app은 TCC가 무시, Swift Mach-O + ad-hoc 코드서명으로 해결
- [fix] launchd PATH 부재 — plist `EnvironmentVariables`에 `/opt/homebrew/bin` 등 추가
- [fix] `brain.py` claude CLI → `/opt/homebrew/bin/claude` 풀패스 (launchd 환경 대응)
- [fix] `alf.py` traceback 로깅 추가 — 에러 원인 추적 개선
- [feat] 웹 접근 기능 추가 — MCP fetch 서버 + WebFetch를 `--allowedTools`로 활성화
- [feat] `daemons/` — launchd 데몬 설정 추가
- [feat] `skills/email/` — 이메일 스킬 추가
- [feat] 이메일 전체 본문 확인 — 에이전트 방식 (Read 도구로 `data/emails/{uid}.txt` 직접 읽기)
- [fix] 이메일 HTML 미리보기 → 태그 제거하여 텍스트만 표시
- [fix] 네이버 IMAP IDLE 미지원 → 5분 폴링 방식으로 전환 (#1)
- [feat] `data/` — 데이터 피드 디렉토리 + brain.py 피드 로딩 연동
- [chore] `requirements.txt` 추가

## 2026-03-02 (v3 — E2E 검증 + research 스킬)

- [test] E2E 테스트 완료 — iMessage 송수신, 기억 저장/조회, 모델 선택 모두 정상
- [feat] `skills/research/` — 조사 요청 시 Apple Notes 공유 폴더에 구조화된 리서치 노트 저장
- [feat] `skills/research/save_note.py` — Markdown→HTML 변환 + AppleScript Apple Notes 저장 헬퍼
- [feat] `src/alf.py` — `[NOTE:제목]...[/NOTE]` 프로토콜 파싱 → Apple Notes 저장 + iMessage 알림
- [change] 모델 전략 변경 — haiku/sonnet 분리 → sonnet 통일 (스킬 프로토콜 정확도 우선)
- [infra] Apple Notes "Afred" 공유 폴더 설정 (bot↔main 계정 공동 작업)

## 2026-03-02 (v2 — 아키텍처 리팩토링)

- [feat] `src/brain.py` — 프롬프트 조립 + Claude 호출 + 모델 자동 선택
- [feat] `src/memory.py` — 메모리 읽기/쓰기, `[MEM:xxx]` 파싱, history.jsonl 로깅
- [feat] `skills/` 시스템 — `_base.md` 페르소나, memory/calendar/notes SKILL.md
- [refactor] `src/alf.py` — 배선만 담당, 로직을 brain/memory로 분리, session_id 제거
- [chore] `.env` — `ALF_MODEL_CHAT`, `ALF_MODEL_MEMORY` 추가
- [chore] `.gitignore` — `memory/` 제외 추가
- [docs] CLAUDE.md — 새 아키텍처/데이터 흐름/스킬 시스템 반영

## 2026-03-02 (v1 — POC)

- [feat] iMessage 수신/발신 POC 구현 (`src/alf.py`) — chat.db 폴링 → Claude sonnet 호출 → osascript 답장
- [chore] `.env.example` 추가 — ALF_MY_NUMBER 설정 템플릿
- [chore] `.gitignore`, `.env` 설정
- 프로젝트 생성 (Alfred/Alf)
- CLAUDE.md 작성 — 콘셉트, 아키텍처, 제약조건 정의
- 아이디어 스케치 완료

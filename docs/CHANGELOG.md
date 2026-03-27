# Alf — Changelog

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

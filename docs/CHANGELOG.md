# Alf — Changelog

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

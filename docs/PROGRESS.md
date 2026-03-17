# Alf — Progress

## Phase 1: 기억하는 비서
- [x] 프로젝트 세팅 (폴더, git, CLAUDE.md)
- [x] 기술 스택 결정 (Python3 + claude -p + osascript)
- [x] iMessage 수신/발신 PoC
- [x] 메모리 구조 설계 (Markdown 파일 기반 → SQLite 전환)
- [x] 아키텍처 리팩토링 (alf.py → brain.py + memory.py 분리)
- [x] 스킬 시스템 구현 (skills/ 디렉토리, YAML frontmatter)
- [x] 기억 프로토콜 구현 ([MEM:xxx] 파싱 → 파일 저장)
- [x] E2E 테스트 (iMessage 송수신, 기억 저장/조회, 모델 선택 검증 완료)
- [x] 모델 전략 결정 (sonnet 통일 — haiku 속도 이점 미미, 스킬 프로토콜 정확도 우선)
- [x] research 스킬 (조사 결과 → Apple Notes 공유 폴더에 구조화 저장)
- [x] 웹 접근 기능 (MCP fetch + WebFetch — 링크 내용 직접 fetch)
- [x] 데이터 피드 시스템 (data/*.json → 프롬프트 자동 주입)
- [x] email 스킬 (요약 + 에이전트 Read로 전체 본문 확인)
- [x] launchd 데몬 등록 (Swift .app + FDA + KeepAlive 크래시 복구)
- [ ] 24시간 안정성 확인

## Phase 2: 먼저 말 거는 비서
- [x] 내장 스케줄러 구현 (at/daily/every + [SCHED:] 프로토콜)
- [x] 세션 컨텍스트 강화 (최근 대화 히스토리 + 활성 스케줄 주입)
- [x] QMD 시맨틱 검색 연동 (과거 대화 recall → 프롬프트 주입)
- [x] 주식 리포트 스킬 (한투 API + 매일 21:00 리포트)
- [x] 장 마감 리포트 스킬 (Claude Code 풀 에이전트 + Apple Notes, 매일 16:00)
- [x] KIS 조회 전용 경로 분리 (`src/kis_readonly_client.py`, `KIS_READONLY_*`)
- [x] KIS 실조회 검증 완료 (지수/국내잔고/체결/미국잔고)
- [ ] 아침 브리핑 스케줄 등록 + 실사용 검증
- [ ] 일정 알림 실사용 검증
- [ ] 24시간 스케줄러 안정성 확인

## Phase 2.5: 아키텍처 전환 (bridge 모드)
- [x] alf_bridge.py — iMessage ↔ inbox/outbox 파일 기반 브릿지
- [x] process_inbox.py — inbox/outbox 헬퍼
- [x] launchd 데몬 등록 (com.alf.bridge)
- [x] launchd 데몬 등록 (com.alf.schedule)
- [x] 1초 폴링 적용
- [x] Claude Code 풀 에이전트 자동 처리 연동 (inbox 감지 → 처리 → outbox)
- [x] GPT Codex OAuth 연동 — process_inbox.py가 GPT-5.4로 자동 처리
- [x] 만기 스케줄 실행 경로 runtime으로 이동 (`src/runtime/scheduler_worker.py`)
- [x] alf.py를 기본 운영 경로에서 퇴역 (`daemon_ctl.py` 기본 집합 제외)
- [ ] alf.py(레거시) + brain.py 완전 제거
- [ ] 24시간 bridge 안정성 확인

## Phase 3: 실행하는 비서
- [ ] 명령 실행 구조
- [ ] 파일 관리
- [ ] 자동화

## Phase 4: Codex Agent Runtime
- [x] `runtime/orchestrator.py` 도입
- [x] 이벤트 버스 초안 도입 (`message.received`, `schedule.due`)
- [x] tool layer 1차 도입 (`memory`, `schedule`, `notes`)
- [x] KIS readonly client 도입 (`src/kis_readonly_client.py`)
- [ ] 메모리 계층 분리 (profile/task/episodic/knowledge/schedule)
- [ ] tool layer 확장 (`email`, `stocks`)
- [ ] proactive notifier 도입
- [ ] `alf.py`, `brain.py` 레거시 제거

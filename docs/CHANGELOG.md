# Alf — Changelog

## 2026-03-03

- [feat] `daemon_ctl.py` — Swift 네이티브 .app 빌드 + launchd 데몬 관리 시스템 구현
- [fix] FDA(전체 디스크 접근) 해결 — 셸 스크립트 .app은 TCC가 무시, Swift Mach-O + ad-hoc 코드서명으로 해결
- [fix] launchd PATH 부재 — plist `EnvironmentVariables`에 `/opt/homebrew/bin` 등 추가
- [fix] `brain.py` claude CLI → `/opt/homebrew/bin/claude` 풀패스 (launchd 환경 대응)
- [fix] `alf.py` traceback 로깅 추가 — 에러 원인 추적 개선
- [feat] 웹 접근 기능 추가 — MCP fetch 서버 + WebFetch를 `--allowedTools`로 활성화
- [feat] `daemons/` — launchd 데몬 설정 추가
- [feat] `skills/email/` — 이메일 스킬 추가
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

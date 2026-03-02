# Alf — Changelog

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

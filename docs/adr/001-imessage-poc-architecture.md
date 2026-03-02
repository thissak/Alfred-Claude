# ADR 001: iMessage POC 아키텍처

## Status
Accepted

## Context
iMessage AI 비서의 첫 POC. "메시지 보내면 Claude가 답장" 동작만 검증하면 됨.
가장 단순한 구조가 필요.

## Decision
- 단일 파일(`src/alf.py`) 무한 루프 방식
- chat.db를 sqlite3 read-only로 2초 폴링 (ROWID 기반)
- Claude 호출은 `claude -p --model sonnet` subprocess (API 아닌 Max 구독 활용)
- iMessage 발신은 osascript로 Messages.app 제어
- 세션 유지는 `--resume` 플래그로 대화 맥락 보존

## Consequences
- 장점: 외부 의존성 없음, 설정 최소, 즉시 검증 가능
- 단점: 프로세스 죽으면 세션 유실, 에러 로깅 없음, 단일 대화 상대만 지원
- P1 진입 시 메모리/로깅/멀티핸들 등 확장 필요

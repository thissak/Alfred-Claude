# ADR 002: Brain/Memory/Skills 분리 아키텍처

## Status
Accepted (supersedes ADR 001)

## Context
POC(ADR 001)에서 alf.py 단일 파일에 모든 로직이 있었음.
P1 "기억하는 비서" 구현을 위해 메모리 관리, 프롬프트 조립, 스킬 시스템이 필요.
단일 파일에 모두 넣으면 유지보수 불가.

## Decision
- `alf.py` — 폴링 + 배선만 (오케스트레이터)
- `brain.py` — 시스템 프롬프트 조립 + Claude 호출 + 메시지 기반 모델 자동 선택
- `memory.py` — Markdown 파일 기반 기억 저장/로딩, `[MEM:xxx]` 파싱, history.jsonl 로깅
- `skills/` — `_base.md` 페르소나 + `*/SKILL.md` YAML frontmatter(`trigger: always | on-demand`)
- 세션(`--resume`) 제거 — 메모리 파일이 맥락 대체

## Consequences
- 장점: 단일 책임, 스킬 추가 시 코어 코드 수정 불필요, 기억 영속화
- 단점: 파일 I/O 증가 (매 메시지마다 memory 전체 로딩), 메모리 파일 크기 관리 필요
- `--resume` 세션 맥락 없이 메모리 파일만으로 충분한지 검증 필요

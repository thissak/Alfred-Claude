# ADR 005: SQLite 메모리 + 내장 스케줄러

## Status
Accepted

## Context
P1 메모리는 Markdown 플랫파일(about.md, calendar.md, notes.md)로 운영 중이었다. 기억이 수십 개 수준에서는 문제 없으나, 축적되면 전체 덤프가 프롬프트 토큰을 낭비한다. 또한 P2(먼저 말 거는 비서)를 위해 알림/리마인더 스케줄링이 필요했다. OpenClaw 분석 결과, 내장 스케줄러 + 구조화된 메모리가 핵심 패턴임을 확인했다.

## Decision

### 메모리: SQLite로 전환
- `memory/alf.db`에 memories, history 테이블
- 선택적 로딩: about 전체, calendar +-7일, notes 최근 30일
- 키워드 검색 지원 (memory.search())
- 기존 .md/.jsonl 파일 자동 마이그레이션 (1회)
- 대화 히스토리를 시스템 프롬프트에 최근 5건 주입

### 스케줄러: 프로세스 내장
- 같은 SQLite DB에 schedules 테이블
- at(1회)/daily(매일)/every(N초 반복) 3종
- [SCHED:] 프로토콜로 Claude가 응답에서 직접 잡 등록
- alf.py 폴링 루프에서 매 사이클 만기 잡 체크

### 외부 의존성 0개
- Python 표준 라이브러리 sqlite3만 사용
- OS cron/launchd 대신 프로세스 내 스케줄링 (단일 프로세스 원칙 유지)

## Consequences
- 메모리가 수백 건으로 늘어나도 프롬프트 토큰 일정하게 유지
- Claude가 대화 맥락을 가지고 응답 가능 (최근 대화 주입)
- P2 핵심 기능(알림/브리핑)의 인프라 확보
- 벡터 임베딩(시맨틱 검색)은 미적용 — API 비용 없이 키워드 검색으로 시작
- 플랫파일 백업/가독성 상실 — 필요 시 export 기능 추가 가능

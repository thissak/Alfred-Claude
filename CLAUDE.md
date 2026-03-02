# Alf — Personal AI Butler

## What is this?

iMessage로 대화하는 개인 AI 비서. Mac Mini 서버에서 24시간 구동.
기억하고, 먼저 말 걸고, 직접 실행하는 AI.

## Architecture

```
[iPhone] ──iMessage──> [Mac Mini 24h Server]
                            ├── Watcher     chat.db polling (SQLite)
                            ├── Brain       claude -p (Max subscription)
                            ├── Memory      Markdown files + SQLite index
                            ├── Scheduler   launchd/cron (proactive)
                            └── Executor    shell commands
```

## Memory Structure

Markdown이 기억, SQLite가 검색엔진. 모든 기억은 사람이 읽을 수 있는 파일.

```
memory/
├── about.md       ← 사용자 정보 (선호, 습관, 프로필)
├── calendar.md    ← 일정/약속
├── notes.md       ← 기억해달라고 한 것들
└── history.jsonl  ← 전체 대화 로그 (raw)
memory.db          ← SQLite 벡터 인덱스 (의미 검색용)
```

- Markdown = 진실의 원천 (투명, 디버깅 쉬움)
- SQLite = 검색 인덱스 (의미 기반 + 키워드)
- history.jsonl = 원본 대화 기록 (append-only)

## Constraints

- Claude Max 구독 사용 (`claude -p` only) — API 최소화
- 모든 데이터 로컬 저장 — 외부 클라우드 의존 없음
- iMessage 단일 채널
- Mac Mini (macOS) 24시간 서버

## Phases

- **P1**: 기억하는 비서 — 대화 기억, 맥락 있는 답변
- **P2**: 먼저 말 거는 비서 — 아침 브리핑, 일정 알림
- **P3**: 실행하는 비서 — 명령 실행, 파일 관리, 자동화

## Tech Stack

- Python 3 + sqlite3 (chat.db 폴링)
- `claude -p --model sonnet` (Claude Max 구독)
- osascript (iMessage 발신)
- python-dotenv (.env 설정)

## Code Style

- 간결함 우선, 추상화 최소
- 단일 책임 — 파일 하나에 역할 하나
- 한글 주석 허용

# Alf — Personal AI Butler

## What is this?

iMessage로 대화하는 개인 AI 비서. Mac Mini 서버에서 24시간 구동.
기억하고, 먼저 말 걸고, 직접 실행하는 AI.

## Architecture

```
[iPhone] ──iMessage──> [Mac Mini 24h Server]
                            ├── alf_bridge.py iMessage ↔ inbox/outbox 브릿지 (1초 폴링)
                            ├── Claude Code   풀 에이전트 (inbox 처리 → outbox 응답)
                            ├── memory.py     SQLite 기반 기억/히스토리 + QMD recall
                            ├── scheduler.py  내장 스케줄러 (at/daily/every)
                            ├── skills/       스킬 디렉토리 (1스킬=1디렉토리)
                            ├── daemon_ctl.py Swift .app 빌드 + launchd 관리
                            └── alf.py        (레거시 — claude -p 방식)
```

## Data Flow (Bridge 모드)

```
iMessage 수신 → alf_bridge.py → run/inbox/*.json
  → Claude Code 풀 에이전트가 처리 (한투 API, Bash, MCP 등 모든 도구 사용)
  → run/outbox/*.json
  → alf_bridge.py → iMessage 발신
```

## Memory Protocol

Claude 응답 끝에 기억 명령 추가 → memory.py가 파싱하여 SQLite 저장:
```
[MEM:about] 커피를 좋아함, 특히 아메리카노
[MEM:calendar] 2026-03-05 14:00 팀 미팅
[MEM:notes] 주말에 세탁기 AS 예약
```

## Schedule Protocol

알림/리마인더 요청 시 Claude가 `[SCHED:]` 태그 출력 → scheduler.py가 파싱하여 DB 등록:
```
[SCHED:at 2026-03-05 14:00] 팀 미팅 30분 전 알림
[SCHED:daily 08:00] 아침 브리핑 해줘
[SCHED:every 3600] 이메일 확인
[SCHED:cancel 3]
```

## Note Protocol

조사 요청 시 `[NOTE:제목]...[/NOTE]` → Apple Notes "Alfred" 폴더에 저장.

## Skills System

- `skills/_base.md` — 항상 로딩되는 베이스 페르소나
- `skills/*/SKILL.md` — YAML frontmatter로 `trigger: always | on-demand`
- 스킬 추가 = 디렉토리 하나 추가. 코어 코드 수정 불필요.

## Model Strategy

- iMessage 자동 응답: GPT-5.4 (Codex OAuth, API 비용 없음)
- 개발/관리: Claude Code RC 세션
- 레거시: sonnet (`claude -p`)

## Constraints

- Claude Max + ChatGPT 구독 사용 — API 최소화
- 모든 데이터 로컬 저장 — 외부 클라우드 의존 없음
- iMessage 단일 채널
- Mac Mini (macOS) 24시간 서버

## Phases

- **P1**: 기억하는 비서 — 대화 기억, 맥락 있는 답변 (완료)
- **P2**: 먼저 말 거는 비서 — 스케줄러 구현 완료, 실사용 검증 중 ← **현재**
- **P3**: 실행하는 비서 — 명령 실행, 파일 관리, 자동화

## Code Style

- 간결함 우선, 추상화 최소
- 단일 책임 — 파일 하나에 역할 하나
- 한글 주석 허용

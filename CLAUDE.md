# Alf — Personal AI Butler

## What is this?

iMessage로 대화하는 개인 AI 비서. Mac Mini 서버에서 24시간 구동.
기억하고, 먼저 말 걸고, 직접 실행하는 AI.

## Architecture

```
[iPhone] ──iMessage──> [Mac Mini 24h Server]
                            ├── alf.py      chat.db 폴링 + 배선
                            ├── brain.py    프롬프트 조립 + Claude 호출
                            ├── memory.py   기억 읽기/쓰기/파싱
                            ├── skills/     스킬 디렉토리 (1스킬=1디렉토리)
                            ├── daemon_ctl.py  Swift .app 빌드 + launchd 관리
                            ├── Scheduler   launchd/cron (P2)
                            └── Executor    shell commands (P3)
```

## Data Flow

```
메시지 수신 → memory.load_all()
  → brain.build_system_prompt(페르소나 + 스킬 + 기억)
  → brain.ask() → claude -p --model {model} --allowedTools "mcp__fetch" "WebFetch" "Read" --system-prompt "..."
  → save_note.parse_and_save() → [NOTE:xxx] 파싱 → Apple Notes 저장
  → memory.parse_and_save() → [MEM:xxx] 파싱 → 파일 저장
  → memory.log_history()
  → send_imessage(클린 응답)
```

## Memory Protocol

Claude 응답 끝에 기억 명령 추가 → memory.py가 파싱하여 파일 저장:
```
[MEM:about] 커피를 좋아함, 특히 아메리카노
[MEM:calendar] 2026-03-05 14:00 팀 미팅
[MEM:notes] 주말에 세탁기 AS 예약
```

## Note Protocol

조사 요청 시 Claude가 `[NOTE:제목]...[/NOTE]` 블록 출력 → save_note.py가 Markdown→HTML 변환 → Apple Notes "Afred" 공유 폴더에 저장:
```
[NOTE:삼성전자 주가 분석]
# 삼성전자 주가 분석
## 요약
...
[/NOTE]
```

## Skills System

- `skills/_base.md` — 항상 로딩되는 베이스 페르소나
- `skills/*/SKILL.md` — YAML frontmatter로 `trigger: always | on-demand`
- 스킬 추가 = 디렉토리 하나 추가. 코어 코드 수정 불필요.

## Model Strategy

```
.env:
ALF_MODEL_CHAT=sonnet      # 일반 대화
ALF_MODEL_MEMORY=sonnet     # 기억 포함 응답
```

sonnet 통일. claude -p CLI 오버헤드로 haiku 속도 이점 미미, 스킬 프로토콜([MEM:], [NOTE:]) 정확도가 더 중요.

## Constraints

- Claude Max 구독 사용 (`claude -p` only) — API 최소화
- 모든 데이터 로컬 저장 — 외부 클라우드 의존 없음
- iMessage 단일 채널
- Mac Mini (macOS) 24시간 서버

## Phases

- **P1**: 기억하는 비서 — 대화 기억, 맥락 있는 답변 ← **현재**
- **P2**: 먼저 말 거는 비서 — 아침 브리핑, 일정 알림
- **P3**: 실행하는 비서 — 명령 실행, 파일 관리, 자동화

## Code Style

- 간결함 우선, 추상화 최소
- 단일 책임 — 파일 하나에 역할 하나
- 한글 주석 허용

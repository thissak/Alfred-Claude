# ADR 007: iMessage Bridge 아키텍처 전환

## Status
Accepted

## Context
기존 구조는 alf.py가 메시지를 수신하면 brain.py를 통해 `claude -p` (pipe 모드)를 subprocess로 호출했다. 이 방식의 한계:
- `claude -p`는 도구 제한적 (Bash, MCP 등 풀 에이전트 기능 사용 불가)
- subprocess 오버헤드 ~7초 (CLI 부팅 지배적)
- 스킬 로딩이 brain.py 커스텀 로직에 의존 (CLAUDE.md, 프로젝트 컨텍스트 미활용)

## Decision
alf.py를 얇은 브릿지(alf_bridge.py)로 교체하고, 파일 기반 IPC로 Claude Code 풀 에이전트와 연동한다.

**새 구조:**
```
iMessage → chat.db → alf_bridge.py(1초 폴링) → run/inbox/*.json
                                                      ↓
                                              Claude Code (풀 에이전트)
                                                      ↓
                                              run/outbox/*.json
                                                      ↓
                                alf_bridge.py(폴링) → iMessage 발신
```

- alf_bridge.py: chat.db 폴링 + inbox 쓰기 + outbox 읽기 + iMessage 발신만 담당
- process_inbox.py: inbox/outbox 파일 조작 헬퍼
- Claude Code 세션 또는 `claude --dangerously-skip-permissions`가 메시지 처리

## Consequences
- Claude Code의 풀 도구(Bash, Read, Write, MCP, WebSearch 등) 사용 가능
- CLAUDE.md, 프로젝트 컨텍스트 자동 로딩
- brain.py의 커스텀 스킬 로딩/세션 관리 불필요
- bridge가 죽어도 메시지가 inbox에 쌓여 유실 없음
- 기존 alf.py + brain.py는 레거시로 유지 (rollback 가능)
- Claude Code 호출 방식(상주 세션 vs 매번 호출) 아직 미확정

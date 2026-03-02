# ADR 003: MCP Fetch로 웹 접근 기능 추가

## Status
Accepted

## Context
Alf는 `claude -p` (pipe mode)로 동작하여 웹 브라우징 도구가 없었음.
iMessage로 링크를 공유해도 내용을 직접 확인할 수 없어, 학습 데이터 기반 추측 답변만 가능.

검토한 대안:
1. Python pre-fetch (alf.py에서 URL 감지 → requests로 fetch → 컨텍스트 주입)
2. OpenClaw 스타일 Gateway (Node.js + Chrome DevTools Protocol)
3. MCP fetch 서버 (`claude -p`의 MCP 도구 지원 활용)

## Decision
MCP fetch 서버(`mcp-server-fetch` via `uvx`) + `--allowedTools` 플래그 사용.

- `claude -p`가 MCP 도구를 지원하므로 코어 코드 최소 변경 (cmd에 `--allowedTools` 2줄 추가)
- Claude가 URL fetch 필요 여부를 자율 판단
- Python pre-fetch 대비 파싱/에러처리 불필요

## Consequences
- brain.py의 cmd 배열에 `--allowedTools "mcp__fetch" "WebFetch"` 추가만으로 완료
- Mac Mini에 `uv` 설치 필요 (`~/.local/bin/uvx`)
- MCP 서버 시작 오버헤드로 응답 시간 소폭 증가 가능
- timeout(현재 60초)이 URL fetch 시 부족할 수 있음

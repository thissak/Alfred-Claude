# ADR 008: GPT Codex OAuth 연동

## Status
Accepted

## Context
기존 Alf는 Claude Max 구독의 `claude -p`로 LLM을 호출했으나 턴당 ~7초 CLI 부팅 오버헤드가 있었다. Claude Code RC(상주 세션)로 전환하면 부팅 없이 가능하지만, inbox 자동 감지/처리가 과제로 남았다. 한편 ChatGPT 구독을 Codex OAuth로 연결하면 API 비용 없이 GPT를 직접 호출할 수 있다는 것을 확인했다.

## Decision
`process_inbox.py`에서 Codex OAuth 토큰(`~/.codex/auth.json`)을 사용하여 GPT-5.4를 직접 호출하는 파이프라인을 추가한다.

- 엔드포인트: `chatgpt.com/backend-api/codex/responses`
- 인증: `codex login --device-auth`로 발급된 OAuth 토큰
- 스트리밍 필수 (`stream: True, store: False`)
- `--watch` 모드로 2초 폴링 자동 처리

## Consequences
- API 비용 없이 GPT-5.4 플래그십 모델 사용 가능
- CLI 부팅 오버헤드 제거 (직접 HTTP 호출)
- 비공식 엔드포인트 — OpenAI가 변경/차단할 수 있음
- Claude Code RC와 병행 가능 (RC는 개발/관리, GPT는 iMessage 자동 응답)
- 토큰 만료 시 재로그인 필요 (자동 갱신은 되나 장기 안정성 미확인)

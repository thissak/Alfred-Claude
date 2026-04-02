# ADR 012: GAN-style 정배열 스크리너 진화 시스템

## Status
Accepted

## Context
정배열 장기 유지 종목을 선별하는 스크리너를 만들되, 프롬프트를 수동으로 튜닝하지 않고 자동으로 진화시키는 시스템이 필요했다. 단순 적중률 측정이 아니라 "계속 진화할 수 있는 구조"가 핵심 요구사항.

## Decision
GAN의 Generator/Discriminator 구조를 차용:
- **Generator**: 프롬프트 파일(`prompts/screener_vNNN.md`)로 정배열 유지 종목 선별
- **Discriminator**: 실제 결과(백데이터)와 대조하여 적중/실패/놓침 분석 + 개선 제안
- **Evolver**: D 피드백으로 다음 버전 프롬프트 자동 생성

프롬프트는 파일로 분리하여 버전 관리. claude -p 호출 시 `--append-system-prompt-file`로 주입하고, `--allowedTools "" --max-turns 1`로 도구 없이 즉시 응답.

과교정 방지 가드레일: 사이클당 2개 조건 변경 제한, 50줄 프롬프트 크기 제한, 최소 3종목 출력 하한선.

## Consequences
- 5년 백데이터로 프롬프트를 수렴시킨 후 실전 투입 가능
- 프롬프트가 투명하게 버전 관리되어 어떤 규칙이 추가/제거되었는지 추적 가능
- claude -p 호출 비용 발생 (사이클당 3회: G, D, evolve)
- 과교정 문제 발견 → 가드레일로 해결 (v001 1KB → v006 14KB 비대화 → 50줄 제한 적용)

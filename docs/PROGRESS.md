# Alf — Progress

## Phase 1: 기억하는 비서
- [x] 프로젝트 세팅 (폴더, git, CLAUDE.md)
- [x] 기술 스택 결정 (Python3 + claude -p + osascript)
- [x] iMessage 수신/발신 PoC
- [x] 메모리 구조 설계 (Markdown 파일 기반)
- [x] 아키텍처 리팩토링 (alf.py → brain.py + memory.py 분리)
- [x] 스킬 시스템 구현 (skills/ 디렉토리, YAML frontmatter)
- [x] 기억 프로토콜 구현 ([MEM:xxx] 파싱 → 파일 저장)
- [x] E2E 테스트 (iMessage 송수신, 기억 저장/조회, 모델 선택 검증 완료)
- [x] 모델 전략 결정 (sonnet 통일 — haiku 속도 이점 미미, 스킬 프로토콜 정확도 우선)
- [x] research 스킬 (조사 결과 → Apple Notes 공유 폴더에 구조화 저장)
- [x] 웹 접근 기능 (MCP fetch + WebFetch — 링크 내용 직접 fetch)
- [x] 데이터 피드 시스템 (data/*.json → 프롬프트 자동 주입)
- [x] email 스킬 추가
- [x] launchd 데몬 등록 (Swift .app + FDA + KeepAlive 크래시 복구)
- [ ] 24시간 안정성 확인

## Phase 2: 먼저 말 거는 비서
- [ ] 스케줄러 설계
- [ ] 아침 브리핑
- [ ] 일정 알림

## Phase 3: 실행하는 비서
- [ ] 명령 실행 구조
- [ ] 파일 관리
- [ ] 자동화

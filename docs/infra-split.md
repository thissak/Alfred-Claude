# 인프라 역할 분리 (2026-03-29)

## 맥미니 (Ai-Mac-mini.local) — 서버

- 데몬 24/7: bridge, inbox, schedule, email, collector, journal-web
- 장마감 리포트 트리거 (16:00)
- iMessage 브릿지 (macOS 전용, 대체불가)
- market.db 원본 보유
- 데몬 설치/관리는 여기서만

## 맥프로 — 워크스테이션

- 주식 분석: /surge, /stock, 스크리닝
- 리서치: 이란전 추적, 뉴스 검색
- 개발: 코드 수정, 스킬 개발, 테스트
- Claude Code 인터랙티브 세션
- **데몬 설치 금지** (daemon_ctl.py install 실행하지 않음)

## 데이터 동기화

rsync 5분 주기로 맥미니 → 맥프로 market.db 복사:

```
*/5 * * * * rsync -az afred@Ai-Mac-mini.local:~/Projects/Alfred-Claude/data/market.db ~/Projects/Alfred-Claude/data/market.db
```

# 인프라 역할 분리 (2026-03-29)

## 맥미니 (Ai-Mac-mini.local) — 서버

- 데몬 24/7: bridge, inbox, schedule, email, collector, journal-web, **market-api**
- 장마감 리포트 트리거 (16:00)
- iMessage 브릿지 (macOS 전용, 대체불가)
- market.db 원본 보유 (읽기+쓰기)
- 데몬 설치/관리는 여기서만

## 맥프로 — 워크스테이션

- 주식 분석: /surge, /stock, 스크리닝
- 리서치: 이란전 추적, 뉴스 검색
- 개발: 코드 수정, 스킬 개발, 테스트
- Claude Code 인터랙티브 세션 (한글 입력 쾌적)
- **데몬 설치 금지** (daemon_ctl.py install 실행하지 않음)

## 데이터 접근: Market API

맥프로에서 market.db에 접근할 때 HTTP API를 사용한다 (rsync 불필요).

**맥미니 (서버)**
- `daemons/market_api.py` — 읽기 전용 SQL 프록시 (port 8001)
- SELECT만 허용, 그 외 403 거부
- 데몬: `python3 daemon_ctl.py install market-api`

**맥프로 (클라이언트)**
- `.zshrc`에 환경변수 추가:
  ```bash
  export MARKET_DB_HOST=Ai-Mac-mini.local:8001
  ```
- `src/market_db.py`가 `MARKET_DB_HOST` 감지 시 자동으로 HTTP API 경유
- 환경변수 미설정 시 로컬 SQLite 직접 접근 (맥미니 기본 동작)

**동작 확인**
```bash
# 맥프로에서 헬스체크
curl http://Ai-Mac-mini.local:8001/health

# 맥프로에서 쿼리 테스트
MARKET_DB_HOST=Ai-Mac-mini.local:8001 python3 -c "
import src.market_db as db
print(db.get_daily_prices('005930', limit=1))
"
```

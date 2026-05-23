# stock-chart (stock.goldenlabs.dev) Handoff

> 작성일: 2026-05-23
> URL: https://stock.goldenlabs.dev (Cloudflare Access OTP, thissak@gmail.com)

## 완료된 작업
- 1단계 MVP — 단일종목 캔들 + 거래량(별도 패널) + 이평선 5/20/60/120 + 호버 OHLCV 레전드 + 크로스헤어 날짜축 (네이버 증권 차트 모사)
- 차트 API — `apps/stock-chart/server.py` (stdlib http.server). `/api/ohlcv`, `/api/search`. `src/market_db.py` 재사용
- 프론트 — `apps/stock-chart/web/index.html` (Lightweight Charts v5, 멀티 패널, 다크 테마)
- 배포 — 맥미니 `daemon_ctl install stock-chart`(8002) + cloudflared 터널 ingress + CF DNS + CF Access(OTP)
- 검증 — 미인증 302 게이트 / `car.goldenlabs.dev` 기존 유지 / 데몬 LISTEN

## 다음 작업
- OTP 로그인 후 차트 실사용 검증 (사용자)
- 2단계 — 두 종목 겹쳐보기 (검색창 2개 + 수익률 정규화). 1단계 API/구조 재사용
- (옵션) 흰 배경 테마, 월/주/년 봉 전환, 거래량 축 숨김

## 알려진 이슈
- `apps/`는 `deploy.sh` 제외 대상 → 차트 코드 변경 시 타깃 rsync 필요:
  `rsync -avz apps/stock-chart/ afred@Ai-Mac-mini.local:/Users/afred/Projects/Alfred-Claude/apps/stock-chart/`
- 데이터 신선도 = collector 일일 수집 의존 (장중 실시간 아님)
- 맥프로 로컬 테스트 서버(127.0.0.1:8002)가 별도로 떠 있을 수 있음 (배포 후 불필요)

## 핵심 결정 사항
- A안(맥미니 올인원) 채택 — ADR 015 참조
- `market-api` 임의 SQL 비노출, 차트 전용 2개 엔드포인트만 노출
- Access 앱 → DNS 순서로 공개 노출 0 보장

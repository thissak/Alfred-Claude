# stock-chart (stock.goldenlabs.dev) Handoff

> 작성일: 2026-05-23 (갱신: 2026-05-24)
> URL: https://stock.goldenlabs.dev (Cloudflare Access OTP, thissak@gmail.com)

## 완료된 작업
- 1단계 MVP — 단일종목 캔들 + 거래량(별도 패널) + 이평선 5/20/60/120 + 호버 OHLCV 레전드 + 크로스헤어 날짜축 (네이버 증권 차트 모사)
- 차트 API — `apps/stock-chart/server.py` (stdlib http.server). `/api/ohlcv`, `/api/search`, `/api/groups`. `src/market_db.py` 재사용
- 프론트 — `apps/stock-chart/web/index.html` (Lightweight Charts v5, 멀티 패널, 다크 테마)
- 배포 — 맥미니 `daemon_ctl install stock-chart`(8002) + cloudflared 터널 ingress + CF DNS + CF Access(OTP)
- **관심그룹 즐겨찾기** — 좌측 사이드바(그룹별 종목+시세, 클릭→차트, ★추가/+그룹/삭제), 서버저장 `data/watchgroups.json`, `watchlist.yaml` 시드
- **기본 차트 범위 전체** + flexbox/autoSize로 시간축 하단 항상 노출
- **과거 데이터 ~30년** — KIS 병렬 백필로 상장일/1990까지 (ADR 016)
- 검증 — OTP 로그인 + 차트 실사용 / 미인증 302 게이트 / `car.goldenlabs.dev` 유지

## 다음 작업
- 2단계 — 두 종목 겹쳐보기 (검색창 2개 + 수익률 정규화). 1단계 API/구조 재사용
- (옵션) 흰 배경 테마, 월/주/년 봉 전환, 거래량 축 숨김

## 알려진 이슈
- `apps/`는 `deploy.sh` 제외 대상 → 차트 코드 변경 시 타깃 rsync 필요:
  `rsync -avz apps/stock-chart/ afred@Ai-Mac-mini.local:/Users/afred/Projects/Alfred-Claude/apps/stock-chart/`
- 데이터 신선도 = collector 일일 수집 의존 (장중 실시간 아님). collector 병렬화+재시도로 누락 위험 완화(ADR 016), freshness 검사기가 갭/정체 독립 감지·알림·자동복구(ADR 017)
- 옛 KIS 일봉 일부는 시가/고저=0(종가만) — DB 플랫화 정정 + 차트 API에서 종가≤0 제외
- 맥프로 로컬 테스트 서버(127.0.0.1:8002)가 별도로 떠 있을 수 있음 (배포 후 불필요)

## 핵심 결정 사항
- A안(맥미니 올인원) 채택 — ADR 015 참조
- `market-api` 임의 SQL 비노출, 차트 전용 엔드포인트만 노출
- Access 앱 → DNS 순서로 공개 노출 0 보장
- KIS 대량 수집은 레이트게이트+재시도 병렬 (백필·collector 공통) — ADR 016

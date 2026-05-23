# ADR 015: stock.goldenlabs.dev 비공개 차트 사이트 배포

## Status
Accepted (2026-05-23)

## Context
개인용 주식 차트 도구(네이버 증권 차트 스타일)를 웹에서 보고 싶음. 일봉 OHLCV 데이터는 맥미니 `market.db`에만 있고, `market-api`(8001)는 임의 SELECT가 되는 SQL 프록시라 로컬/Tailscale 전용으로만 운영 중. 요건:

1. 단일종목 차트 → 두 종목 비교로 확장
2. 어디서나(폰·외부 PC) 접근하되 본인만 (개인 분석 정보)
3. 기존 인프라 재사용, 저비용

호스팅 구조 선택지:
- **A안 (맥미니 올인원)** — UI+API를 한 서버에서 서빙, 기존 cloudflared 터널에 얹음
- **B안 (Vercel + 터널 API)** — notes 방식. 정적 프론트는 Vercel, 데이터는 맥미니 터널. 출처가 둘이라 CORS + CF Access 앱 2개 필요

## Decision
**A안 채택.** `apps/stock-chart/server.py`(stdlib `http.server`, 의존성 0)가 정적 프론트(Lightweight Charts v5)와 `/api/ohlcv`·`/api/search`를 한 포트(8002)에서 서빙. `src/market_db.py` 재사용 — `market-api`의 임의 SELECT 프록시는 인터넷에 노출하지 않고 **차트 전용 2개 엔드포인트만** 노출.

노출/인증:
- 기존 `vw-stylelab` cloudflared 터널 ingress에 `stock.goldenlabs.dev → http://localhost:8002` 추가
- CF DNS proxied CNAME (`cloudflared tunnel route dns`)
- Cloudflare Access 앱 `goldenlabs-stock` + 정책 `me-only`(thissak@gmail.com), 기존 One-time PIN IdP 재사용, 365일 세션 — goldenLabs ADR 001(notes) 패턴 복제
- **보안 순서**: Access 앱을 DNS보다 먼저 생성해 공개 노출 0 보장
- `daemon_ctl.py`에 `stock-chart` 등록 (맥미니 launchd 상시 실행, 로컬 `market.db` 직접 조회)

## Consequences

### 긍정
- UI+데이터 동일 출처 → CORS 없음, CF Access 앱 1개로 전체 보호
- 새 인프라 0 — 기존 터널·Caddy 옆에 ingress 1줄 + CNAME 1개
- `market-api` 임의 SQL은 비노출 유지 (공격면 최소)
- 어디서나 OTP 1회로 접근, 검색엔진 인덱싱 0

### 부정 / 트레이드오프
- 자동배포(Vercel push) 없음 — `apps/`는 `deploy.sh` 제외 대상이라 코드 변경 시 타깃 rsync 필요
- 차트 데이터 신선도는 collector 일일 수집에 의존 (장중 실시간 아님)
- cloudflared 재시작 시 `car.goldenlabs.dev` 수초 끊김

### 자원 식별자
| 자원 | 값 |
|------|-----|
| Access App | `64df4de0-4c95-443f-85af-bedf803a7c4a` |
| Access Policy | `c1e66deb-96ba-441a-87a1-e0c2eda38ee4` |
| Application AUD | `175c5999924d54b1afeba57bfafe72f23eec67db972bd6e5e3f1822e72115dce` |
| IdP (One-time PIN, 재사용) | `714f0d04-652f-4219-9127-0e8c7a6c9d54` |
| 터널 | `vw-stylelab` (`dcab3bc6-e076-4c63-99cd-a3b3ef07db93`) |
| 데몬 | `com.alf.stock-chart` (port 8002, 맥미니) |

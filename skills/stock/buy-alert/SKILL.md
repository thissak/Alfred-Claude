---
name: buy-alert
description: 분석한 종목의 매수 조건을 등록/해제한다
trigger: on-demand
---

# 매수 알림 등록

종목 분석 후 매수 타이밍 포착 조건을 등록한다.
등록된 조건은 맥미니 데몬이 매일 장 마감 후 체크하여 iMessage로 알림.

## 트리거

"등록해줘", "매수 등록", "알림 등록", "알림 해제", "알림 목록"

## 동작

### 등록

1. 대화 컨텍스트에서 추출:
   - 종목코드 + 종목명
   - 매수 목표 가격 (price_low, price_high)
   - 매수 사유 (reason) — 분석에서 나온 핵심 근거
   - 매수 전략 (strategy) — 분할 비율, 금액 등
2. `data/buy_alerts.yaml` 읽기
3. alerts 리스트에 새 항목 추가:

```yaml
- code: "234690"
  name: 녹십자웰빙
  price_low: 12000        # 이 가격 이하 도달 시 알림 (필수)
  price_high: 13000       # 목표 범위 상단 (선택)
  reason: "RSI 과매수 해소 + 눌림목 대기"
  strategy: "분할매수 1차 30%"
  registered: "2026-03-29"
  expires: "2026-06-30"   # 기본 3개월
  enabled: true
```

4. yaml 파일 Write
5. 응답: "{종목명} {price_low}원 이하 도달 시 알림 등록했습니다. 유효기간: {expires}"

### 해제

1. `data/buy_alerts.yaml` 읽기
2. 해당 종목의 `enabled: false` 설정
3. yaml 파일 Write
4. 응답: "{종목명} 매수 알림을 해제했습니다"

### 목록 조회

1. `data/buy_alerts.yaml` 읽기
2. 활성(enabled: true) 항목만 표시:

```
매수 알림 목록:
1. 녹십자웰빙 (234690) — 12,000원 이하 | ~2026-06-30
   사유: RSI 과매수 해소 + 눌림목 대기
2. ...
```

## 규칙

- 종목코드를 모르면 종목명으로 검색하여 확인
- price_low는 반드시 숫자 (쉼표 제거)
- expires 미지정 시 등록일로부터 3개월
- 같은 종목 중복 등록 시 기존 건 덮어쓰기 (enabled: true로 갱신)
- yaml 파일이 없으면 새로 생성

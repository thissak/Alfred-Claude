---
name: surge
description: >-
  종목 일봉 이상패턴 분석 + 뉴스·수급 연동. 급등/급락/거래량폭증/갭/장대봉/꼬리봉을
  자동 탐지하고 해당 날짜의 뉴스 촉매와 외인·기관 수급을 매칭.
  "급등 분석", "이상패턴", "왜 올랐어", "왜 빠졌어", "surge", "종목 분석" 키워드에 반응.
argument-hint: "<종목코드> [종목명]"
---

# 종목 이상패턴 분석 (일봉 + 뉴스 + 수급)

종목코드를 받아 일봉 데이터에서 이상 패턴을 탐지하고, 해당 날짜의 뉴스·수급을 매칭하여 "왜 움직였나"를 시계열로 분석한다.

## 실행 절차

### Step 1: 인자 파싱

`<종목코드> [종목명]` 형태로 인자를 받는다.
- 종목코드: 6자리 숫자 (필수)
- 종목명: 한글 이름 (선택, 리포트 제목용)

종목코드 없이 종목명만 주어진 경우 `data/stock.json`의 watchlist에서 코드를 찾는다.

### Step 2: 분석 스크립트 실행

```bash
python3 scripts/stock_surge_analysis.py <종목코드> <종목명>
```

출력에서 이상패턴 테이블을 확인한다.

### Step 3: 차트 생성

```bash
python3 scripts/stock_surge_chart.py <종목코드> <종목명>
```

차트가 `data/stock-analysis/<종목코드>_chart.png`에 저장된다.
Read 도구로 차트 이미지를 사용자에게 보여준다.

차트를 노션에 삽입하기 위해 GitHub에 push한다:
```bash
git add -f data/stock-analysis/<종목코드>_chart.png
git commit -m "chore: add <종목명> surge chart"
git push
```
노션 이미지 URL: `https://raw.githubusercontent.com/thissak/Alfred-Claude/main/data/stock-analysis/<종목코드>_chart.png`

### Step 4: 분석 리포트 제공

스크립트 출력 테이블 + 차트를 함께 보여주며, 핵심 인사이트를 정리한다:

인사이트 정리 기준:
- 급등/급락의 뉴스 촉매가 무엇이었나
- 수급 주체 (외인 vs 기관 vs 개인)가 누구였나
- 거래량 폭증이 동반됐는가
- 급락 후 반등 패턴이 있었는가
- 외인/기관이 급락 시 역매수했는가

### Step 5: 노션 저장

`/stock-notion` 스킬을 호출하여 노션에 저장한다.
- 인자: `<종목코드> <종목명>`
- stock-notion 스킬이 종합분석 + 패턴 + 차트를 노션 페이지로 생성
- Step 3에서 이미 차트를 push했으므로 stock-notion은 차트 생성/push를 건너뛴다
- surge 분석 결과(이상패턴 테이블, 인사이트)를 stock-notion 페이지 내용에 포함시킨다

### Step 6: 매매 기준 리마인드

사용자의 매매 패턴 피드백을 반영한다:
- 매수 기준: 급락 후 진입 (사용자 강점)
- 매도 기준: 반드시 진입 전 설정 필요 (목표가, 손절가, 보유기간)
- 음봉 하나는 매도 신호가 아님을 리마인드

## 규칙
- 탐지 기준: 등락 ±5%, 거래량 5일평균 3배+, 갭 ±3%, 장대봉 몸통70%+변동7%+, 꼬리봉 60%+
- 뉴스에서 인포스탁 순위 기사는 자동 필터링
- 투자자 동향은 최근 30일만 조회 가능 (API 제한)

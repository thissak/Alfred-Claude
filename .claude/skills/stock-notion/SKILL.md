---
name: stock-notion
description: >-
  종목 분석 결과를 노션 페이지로 저장하는 스킬. 종합분석(펀더멘털+수급+패턴) +
  일봉차트를 생성하여 노션에 정리한다. 셀바스AI 리포트 포맷 기준.
  "노션 저장", "종목 노션", "stock notion", "노션에 정리" 키워드에 반응.
argument-hint: "<종목코드|종목명> [관심 이유]"
---

# 종목 분석 → 노션 페이지 저장

종목코드를 받아 종합 분석 → 차트 생성 → 노션 페이지 생성까지 수행한다.

## Step 1: 인자 파싱

`<종목코드|종목명> [관심 이유]` 형태.
- 첫 번째: 종목코드(6자리) 또는 종목명
- 나머지: 관심 이유 (선택, 페이지 상단에 표시)

종목명만 주어진 경우 market.db에서 검색:
```bash
MARKET_DB_HOST=Ai-Mac-mini.local:8001 python3 -c "
from src.market_db import _query
rows = _query(\"SELECT code, name FROM securities WHERE name LIKE '%종목명%'\", [])
for r in rows: print(r['code'], r['name'])
"
```

## Step 2: 중복 확인

노션에서 같은 종목·같은 날짜 페이지가 있는지 검색한다.
```
notion-search: "{종목명} {오늘날짜}"
```
이미 있으면 사용자에게 알리고 스킵.

## Step 3: 데이터 수집

### 3-1. 종합 분석
```bash
MARKET_DB_HOST=Ai-Mac-mini.local:8001 python3 scripts/stock_analysis.py <종목코드> <종목명>
```
결과: `data/stock-analysis/<종목코드>_analysis.json`

### 3-2. 이상패턴 탐지
```bash
MARKET_DB_HOST=Ai-Mac-mini.local:8001 python3 scripts/stock_surge_analysis.py <종목코드> <종목명>
```

## Step 4: 차트 생성 + GitHub 업로드

```bash
MARKET_DB_HOST=Ai-Mac-mini.local:8001 python3 scripts/stock_surge_chart.py <종목코드> <종목명>
git add -f data/stock-analysis/<종목코드>_chart.png
git commit -m "chore: add <종목명> chart"
git push
```

차트 URL: `https://raw.githubusercontent.com/thissak/Alfred-Claude/main/data/stock-analysis/<종목코드>_chart.png`

Read 도구로 차트 이미지를 사용자에게 보여준다.

## Step 5: 분석 내용 정리

JSON + 패턴 분석 결과를 읽고 아래를 작성한다:

**인사이트 (3-5개):**
- 수급 주체/방향, 이평선 배열, 실적 흐름, 촉매 이벤트

**리스크 (2-4개):**
- 밸류에이션 부담, 수급 이탈, 실적 악화, 과열 지표

## Step 6: 노션 페이지 생성

`notion-create-pages`로 생성. 템플릿은 [notion-page-template.md](notion-page-template.md) 참조.

- **부모**: "AI 종목 분석" (page_id: `332b83e1-2dd9-81f5-8c45-d990bb3b87fc`)
- **제목**: `📊 {종목명} ({종목코드}) — {오늘 날짜}`
- **아이콘**: 📊

### 노션 포맷 핵심 규칙
- 테이블: Notion `<table header-row="true">` 포맷 사용
- 급등 행: `<td><span style="green_background">값</span></td>`
- 급락 행: `<td><span style="red_background">값</span></td>`
- 이미지: `![alt](github-raw-url)`
- 뉴스 중 인포스탁/서울데이터랩/광고성 기사 필터링

## Step 7: 결과 보고

1. 차트 이미지 표시
2. 핵심 인사이트 3줄 요약
3. 노션 페이지 URL

---
name: daily-report
description: 장 마감 리포트 — 한투 API 데이터 수집 + Claude 분석 → Apple Notes 저장
trigger: on-demand
---

# 장 마감 리포트

한국투자증권 OpenAPI로 데이터를 수집하고, 분석하여 Apple Notes "Alfred" 폴더에 리포트를 저장한다.

## 실행 순서

1. `python3 skills/stock/fetch_stock.py` 실행하여 최신 데이터 수집
2. `data/stock.json` 읽기
3. 필요 시 한투 API로 추가 데이터 수집 (일봉, 기술적 지표 등)
4. 아래 리포트 형식으로 분석 작성
5. Apple Notes "Alfred" 폴더에 저장 (`skills/research/save_note.py` 활용)

## 리포트 형식

```markdown
# 장 마감 리포트 (M/DD)

## 시장 요약
KOSPI/KOSDAQ 지수, 등락률, 한 줄 시황 코멘트

## 내 포트폴리오
보유종목 현황, 총 평가손익, 주목할 변동

## 관심종목 동향
watchlist 종목별 시세 + 간단 코멘트

## 오늘의 특징주
급등/급락, 거래량 상위, 외인/기관 수급 특이점

## 기술적 분석 (주요 종목)
이평선 배열, RSI, MACD 등 핵심 지표 요약

## 내일 주목할 점
시장 이벤트, 수급 흐름, 기술적 관점 전망
```

## Apple Notes 저장 방법

```python
import sys
sys.path.insert(0, 'skills/research')
from save_note import md_to_html, _save_to_notes

html = md_to_html(report_markdown)
_save_to_notes(f"장 마감 리포트 ({date})", html)
```

## 규칙
- 데이터는 한투 API 우선 (웹 검색 fallback)
- 수치는 읽기 쉽게 만/억 단위 변환
- 분석은 간결하되 인사이트 포함
- 손실은 사실만 전달, 감정 배제

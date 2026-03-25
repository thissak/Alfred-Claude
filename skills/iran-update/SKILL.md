---
name: iran-update
description: >-
  이란전 최신 업데이트. Claude WebSearch + GPT Codex 양쪽으로 검색하여
  병합 리포트 생성. "이란전 업데이트", "이란 전쟁", "iran update" 키워드에 반응.
argument-hint: "[save]"
---

# 이란전 업데이트 스킬

이란전 최신 상황을 Claude WebSearch와 GPT Codex 양쪽에서 검색하여 병합 리포트를 생성한다.

## 실행 절차

### Step 1: 병렬 검색

두 소스를 **동시에** 실행한다:

**Claude 채널** — WebSearch 3회:
1. `Iran Israel war latest update {today} military situation`
2. `Iran war ceasefire negotiations Trump {today}`
3. `Brent crude oil Hormuz strait KOSPI VIX {today}`

**GPT 채널** — Bash로 codex exec 실행:
```
/opt/homebrew/bin/codex exec "Give me the latest Iran war update as of {today}. Cover: 1) Military situation 2) Ceasefire/diplomacy 3) Energy markets (Brent, Hormuz) 4) Economic indicators (VIX, Asian markets). Be factual, cite sources. Search the web." 2>&1 | head -80
```

### Step 2: 병합 리포트 작성

5개 분석 축으로 정리한다:

| 축 | 내용 |
|---|---|
| 1. 군사 상황 | 주요 공격/방어, 전선 변화, 사상자 |
| 2. 트럼프 출구 전략 | 미국 입장, 모순/변화, 병력 동향 |
| 3. 이란 에너지 인질 전략 | 호르무즈 봉쇄, 걸프국 인프라, 위협/실행 |
| 4. 삼각 교착 분석 | 이스라엘↔트럼프↔이란 구조 변화, 핵심 변화점 |
| 5. 경제 지표 | 브렌트 유가, VIX, KOSPI, 호르무즈 통행량, 환율 |

### Step 3: 출력 형식

```
## 이란전 Day {N} 업데이트 ({today})

### 1. 군사 상황
- ...

### 2. 트럼프 출구 전략
- ...

### 3. 이란 에너지 인질 전략
- ...

### 4. 삼각 교착 분석
- ...

### 5. 경제 지표
| 지표 | 수치 | 전일비 |
|------|------|--------|
| 브렌트 유가 | | |
| VIX | | |
| KOSPI | | |
| 호르무즈 | | |

### Claude vs GPT 차이점
| | Claude | GPT |
|---|---|---|
| 핵심 프레임 | | |
| 유가 수치 | | |
| 고유 인사이트 | | |

Sources:
- [출처1](url)
- [출처2](url)
```

### Step 4: 파일 저장 (옵션)

`save` 인자가 있거나 사용자가 저장을 요청하면:
- `docs/iran-war/daily/{today}.md`에 리포트 저장
- 기존 파일이 있으면 덮어쓰기 전 확인

## 규칙
- 전쟁 시작일: 2026-02-28 (Day 계산 기준)
- GPT 응답은 영어로 받아도 됨 — 병합 리포트는 한국어
- 두 소스의 수치가 다르면 양쪽 모두 표기하고 출처 명시
- 분석 축 5개는 고정, 새로운 중대 변화 발생 시 "핵심 변화" 섹션 추가
- codex timeout은 120초

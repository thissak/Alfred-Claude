# ADR 010: 메모리 전체 로드 + Compaction 전략

## Status
Accepted

## Context
기존 메모리 시스템은 QMD 외부 바이너리(BM25 검색)와 선택적 로딩(about 전체, calendar +-7일, notes 30일)을 사용했다. 문제점:
- QMD 외부 의존 → 바이너리 없으면 시맨틱 검색 전체 실패
- DB → .md 파일 → qmd 인덱스 이중 동기화 부담
- FTS5로 전환 시도했으나 한국어 토큰 매칭 한계 ("삼성" ≠ "삼성전자")
- 벡터 검색은 임베딩 API 의존 + 오버엔지니어링

한편 Claude Opus 4.6은 1M 토큰 컨텍스트를 지원하며, 현재 메모리+히스토리 전체가 ~35K 토큰(3.5%)에 불과하다.

## Decision
검색 인프라(QMD, FTS5, 벡터)를 제거하고 전체 메모리+히스토리를 시스템 프롬프트에 주입한다. LLM 자체가 시맨틱 검색 엔진 역할을 수행한다.

스케일 대비를 위해 compaction 메커니즘을 도입한다:
- 히스토리 500건 초과 시 자동 트리거
- 최근 50건은 원문 유지
- 나머지는 Claude haiku로 날짜별 요약 → `memories(type=episode)`로 저장
- 원본 히스토리 삭제

## Consequences
- 외부 의존(qmd 바이너리) 완전 제거, data/qmd/ 디렉토리 불필요
- 코드 대폭 단순화 (recall.py, history.py 어댑터 불필요)
- 시맨틱 매칭 품질 향상 (LLM이 직접 판단)
- Anthropic 공식 문서의 "context rot" 경고에 따라, 데이터가 50K+ 토큰으로 성장하면 compaction 임계값 조정 필요
- compaction 시 haiku API 비용 발생 (미미)

# 노션 페이지 템플릿

아래는 `notion-create-pages`의 `content` 파라미터에 넣을 Notion Markdown 템플릿이다.
셀바스AI (108860) 리포트를 레퍼런스로 한다.

## 템플릿

```notion-markdown
## 분석 요약

<table header-row="true">
<tr>
<td>항목</td>
<td>값</td>
</tr>
<tr>
<td>시장 / 섹터</td>
<td>{market} / {sector}</td>
</tr>
<tr>
<td>종가</td>
<td>{close}원</td>
</tr>
<tr>
<td>시가총액</td>
<td>{mktcap}억원</td>
</tr>
<tr>
<td>PER / PBR</td>
<td>{per} / {pbr}</td>
</tr>
<tr>
<td>외인비율</td>
<td>{foreign_ratio}%</td>
</tr>
<tr>
<td>5일 수익률</td>
<td>{return_5d}%</td>
</tr>
</table>

> **관심 이유**: {reason}

## 차트

![{name} 일봉차트](https://raw.githubusercontent.com/thissak/Alfred-Claude/main/data/stock-analysis/{code}_chart.png)

## 핵심 패턴 + 뉴스 촉매

<table header-row="true">
<tr>
<td>날짜</td>
<td>종가</td>
<td>등락</td>
<td>거래량</td>
<td>패턴</td>
<td>외인</td>
<td>기관</td>
<td>뉴스 촉매</td>
</tr>
<tr>
<td><span style="green_background">03-24</span></td>
<td><span style="green_background">13,160</span></td>
<td><span style="green_background">+22.9%</span></td>
<td><span style="green_background">13.4x</span></td>
<td><span style="green_background">급등, 거래량13배</span></td>
<td><span style="green_background">+108,215</span></td>
<td><span style="green_background">+94,794</span></td>
<td><span style="green_background">아마존·바이두 협업 모빌리티 AI</span></td>
</tr>
<tr>
<td><span style="red_background">03-04</span></td>
<td><span style="red_background">9,330</span></td>
<td><span style="red_background">-15.8%</span></td>
<td><span style="red_background">1.6x</span></td>
<td><span style="red_background">급락</span></td>
<td><span style="red_background">+107,769</span></td>
<td><span style="red_background">+3,818</span></td>
<td><span style="red_background"></span></td>
</tr>
</table>

## 인사이트

1. {insight_1}
2. {insight_2}
3. {insight_3}

## 리스크

1. {risk_1}
2. {risk_2}

---

*생성: {date} | 데이터: market.db (KIS API)*
```

## 색상 규칙

- **급등** (등락 +5% 이상): 행 전체에 `<span style="green_background">` 적용
- **급락** (등락 -5% 이하): 행 전체에 `<span style="red_background">` 적용
- **거래량 폭증** (3배 이상, 등락 ±5% 미만): 배경색 없이 볼드 처리
- **일반 행**: 배경색 없음

## 주의사항

- Notion 테이블은 `<table>` 태그 사용 — 일반 Markdown 테이블 `| |` 사용 금지
- `<table header-row="true">`로 헤더 행 지정
- 각 셀은 `<td>` 태그 안에 내용 작성
- 이미지 URL은 GitHub raw URL 사용 (push 후 접근 가능)
- 페이지 제목은 content에 넣지 말고 properties.title에만 넣는다

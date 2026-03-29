# 한국투자증권 (KIS) Open API 전체 엔드포인트 카탈로그

조사일: 2026-03-28
소스: KIS Developers Portal, GitHub open-trading-api, 공식 문서

---

## 0. 인증 (OAuth)

| # | API명 | tr_id | Method | URL Path | 주요 파라미터 | 과거조회 | 페이징 |
|---|-------|-------|--------|----------|-------------|---------|--------|
| 1 | 접근토큰 발급 | - | POST | `/oauth2/tokenP` | grant_type, appkey, appsecret | N | N |
| 2 | 접근토큰 폐기 | - | POST | `/oauth2/revokeP` | token | N | N |
| 3 | Hashkey 생성 | - | POST | `/uapi/hashkey` | body 데이터 | N | N |
| 4 | WebSocket 접속키 발급 | - | POST | `/oauth2/Approval` | grant_type, appkey, secretkey | N | N |

---

## 1. 국내주식 시세 (Quotations)

### 1-1. 기본시세 (REST)

| # | API명 | tr_id | Method | URL Path | 주요 파라미터 | 과거조회 | 페이징 |
|---|-------|-------|--------|----------|-------------|---------|--------|
| 1 | 주식현재가 시세 | FHKST01010100 | GET | `/uapi/domestic-stock/v1/quotations/inquire-price` | fid_cond_mrkt_div_code(J/NX/UN), fid_input_iscd(종목코드) | N | N |
| 2 | 주식현재가 시세2 | FHPST01010000 | GET | `/uapi/domestic-stock/v1/quotations/inquire-price-2` | fid_cond_mrkt_div_code, fid_input_iscd | N | N |
| 3 | 주식현재가 체결 | FHKST01010300 | GET | `/uapi/domestic-stock/v1/quotations/inquire-ccnl` | fid_cond_mrkt_div_code, fid_input_iscd | N | N |
| 4 | 주식현재가 일자별 | FHKST01010400 | GET | `/uapi/domestic-stock/v1/quotations/inquire-daily-price` | fid_input_iscd, fid_period_div_code(D/W/M), fid_org_adj_prc | N (최근30건) | N |
| 5 | 주식현재가 호가/예상체결 | FHKST01010200 | GET | `/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn` | fid_cond_mrkt_div_code, fid_input_iscd | N | N |
| 6 | 주식현재가 투자자 | FHKST01010900 | GET | `/uapi/domestic-stock/v1/quotations/inquire-investor` | fid_cond_mrkt_div_code, fid_input_iscd | N | N |
| 7 | 주식현재가 회원사 | FHKST01010600 | GET | `/uapi/domestic-stock/v1/quotations/inquire-member` | fid_cond_mrkt_div_code, fid_input_iscd | N | N |
| 8 | 주식현재가 당일시간대별체결 | FHPST01060000 | GET | `/uapi/domestic-stock/v1/quotations/inquire-time-itemconclusion` | fid_input_iscd, fid_input_hour_1 | N | Y |
| 9 | 국내주식기간별시세(일/주/월/년) | FHKST03010100 | GET | `/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice` | fid_input_iscd, fid_input_date_1, fid_input_date_2, fid_period_div_code(D/W/M/Y) | **Y** | Y |
| 10 | 국내주식분봉차트 | FHKST03010200 | GET | `/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice` | fid_input_iscd, fid_input_hour_1, fid_pw_data_incu_yn | N (당일만) | Y |
| 11 | 일별거래량매매동향 | FHKST03010800 | GET | `/uapi/domestic-stock/v1/quotations/inquire-daily-trade-volume` | fid_input_iscd, fid_input_date_1, fid_input_date_2 | **Y** | Y |
| 12 | ELW현재가 | FHKEW15010000 | GET | `/uapi/domestic-stock/v1/quotations/inquire-elw-price` | fid_cond_mrkt_div_code, fid_input_iscd | N | Y |
| 13 | 뉴스/공시 제목 | FHKST01011800 | GET | `/uapi/domestic-stock/v1/quotations/news-title` | fid_input_iscd, fid_input_date_1, fid_news_ofer_entp_code | **Y** | Y |

### 1-2. 시간외시세

| # | API명 | tr_id | Method | URL Path | 주요 파라미터 | 과거조회 | 페이징 |
|---|-------|-------|--------|----------|-------------|---------|--------|
| 14 | 시간외현재가 | FHPST02300000 | GET | `/uapi/domestic-stock/v1/quotations/inquire-overtime-price` | fid_cond_mrkt_div_code, fid_input_iscd | N | N |
| 15 | 시간외일자별주가 | FHPST02320000 | GET | `/uapi/domestic-stock/v1/quotations/inquire-daily-overtimeprice` | fid_input_iscd | N (최근30건) | N |
| 16 | 시간외호가(KRX) | - | GET | `/uapi/domestic-stock/v1/quotations/overtime-asking-price-krx` | fid_input_iscd | N | N |
| 17 | 시간외체결(KRX) | - | GET | `/uapi/domestic-stock/v1/quotations/overtime-ccnl-krx` | fid_input_iscd | N | N |
| 18 | 시간외예상체결(KRX) | - | GET | `/uapi/domestic-stock/v1/quotations/overtime-exp-ccnl-krx` | fid_input_iscd | N | N |
| 19 | 시간외예상거래등락 | - | GET | `/uapi/domestic-stock/v1/quotations/overtime-exp-trans-fluct` | - | N | Y |
| 20 | 시간외등락률 | - | GET | `/uapi/domestic-stock/v1/quotations/overtime-fluctuation` | - | N | Y |
| 21 | 시간외거래량 | - | GET | `/uapi/domestic-stock/v1/quotations/overtime-volume` | - | N | Y |

### 1-3. 투자자/외국인/기관

| # | API명 | tr_id | Method | URL Path | 주요 파라미터 | 과거조회 | 페이징 |
|---|-------|-------|--------|----------|-------------|---------|--------|
| 22 | 외국계/기관 종합 | FHPTJ04400000 | GET | `/uapi/domestic-stock/v1/quotations/foreign-institution-total` | fid_input_iscd, fid_div_cls_code, fid_rank_sort_cls_code, fid_etc_cls_code | N | N |
| 23 | 종목별 투자자 일별매매동향 | FHPTJ04160001 | GET | `/uapi/domestic-stock/v1/quotations/investor-trade-by-stock-daily` | fid_input_iscd | **Y** | Y |
| 24 | 시장별 투자자 일별매매동향 | - | GET | `/uapi/domestic-stock/v1/quotations/inquire-investor-daily-by-market` | - | **Y** | Y |
| 25 | 시장별 투자자 시간별매매동향 | - | GET | `/uapi/domestic-stock/v1/quotations/inquire-investor-time-by-market` | - | N | Y |
| 26 | 투자자 매매동향 추정 | - | GET | `/uapi/domestic-stock/v1/quotations/investor-trend-estimate` | - | N | N |
| 27 | 외국계 매수추정 동향 | - | GET | `/uapi/domestic-stock/v1/quotations/frgnmem-pchs-trend` | fid_input_iscd | N | Y |
| 28 | 외국계 매매추정 동향 | - | GET | `/uapi/domestic-stock/v1/quotations/frgnmem-trade-trend` | fid_input_iscd | N | Y |
| 29 | 외국계 매매추정 예측 | - | GET | `/uapi/domestic-stock/v1/quotations/frgnmem-trade-estimate` | fid_input_iscd | N | N |

### 1-4. 프로그램매매

| # | API명 | tr_id | Method | URL Path | 주요 파라미터 | 과거조회 | 페이징 |
|---|-------|-------|--------|----------|-------------|---------|--------|
| 30 | 프로그램매매 종목별(체결) | FHPPG04650101 | GET | `/uapi/domestic-stock/v1/quotations/program-trade-by-stock` | fid_input_iscd | N | Y |
| 31 | 프로그램매매 종목별(일별) | - | GET | `/uapi/domestic-stock/v1/quotations/program-trade-by-stock-daily` | fid_input_iscd | **Y** | Y |
| 32 | 프로그램매매(KRX) | - | GET | `/uapi/domestic-stock/v1/quotations/program-trade-krx` | - | N | Y |
| 33 | 프로그램매매(NXT) | - | GET | `/uapi/domestic-stock/v1/quotations/program-trade-nxt` | - | N | Y |
| 34 | 프로그램매매(통합) | - | GET | `/uapi/domestic-stock/v1/quotations/program-trade-total` | - | N | Y |
| 35 | 업종 프로그램매매 | - | GET | `/uapi/domestic-stock/v1/quotations/index-program-trade` | - | N | Y |
| 36 | 종목비교 프로그램매매(당일) | - | GET | `/uapi/domestic-stock/v1/quotations/comp-program-trade-today` | - | N | Y |
| 37 | 종목비교 프로그램매매(일별) | - | GET | `/uapi/domestic-stock/v1/quotations/comp-program-trade-daily` | - | **Y** | Y |
| 38 | 투자자별 프로그램매매(당일) | - | GET | `/uapi/domestic-stock/v1/quotations/investor-program-trade-today` | - | N | Y |

### 1-5. 업종/지수

| # | API명 | tr_id | Method | URL Path | 주요 파라미터 | 과거조회 | 페이징 |
|---|-------|-------|--------|----------|-------------|---------|--------|
| 39 | 업종현재지수 | FHPUP02100000 | GET | `/uapi/domestic-stock/v1/quotations/inquire-index-price` | fid_cond_mrkt_div_code(U), fid_input_iscd(업종코드) | N | Y |
| 40 | 업종일자별시세 | - | GET | `/uapi/domestic-stock/v1/quotations/inquire-index-daily-price` | fid_input_iscd | N (최근30건) | N |
| 41 | 업종틱시세 | - | GET | `/uapi/domestic-stock/v1/quotations/inquire-index-tickprice` | fid_input_iscd | N | N |
| 42 | 업종시간별시세 | - | GET | `/uapi/domestic-stock/v1/quotations/inquire-index-timeprice` | fid_input_iscd | N | N |
| 43 | 업종기간별시세(일/주/월) | - | GET | `/uapi/domestic-stock/v1/quotations/inquire-daily-indexchartprice` | fid_input_iscd, fid_input_date_1, fid_input_date_2 | **Y** | Y |
| 44 | 업종분봉차트 | - | GET | `/uapi/domestic-stock/v1/quotations/inquire-time-indexchartprice` | fid_input_iscd | N | Y |
| 45 | 업종체결 | - | GET | `/uapi/domestic-stock/v1/quotations/index-ccnl` | fid_input_iscd | N | N |
| 46 | 업종예상체결 | - | GET | `/uapi/domestic-stock/v1/quotations/index-exp-ccnl` | fid_input_iscd | N | N |
| 47 | 업종별종목시세 | - | GET | `/uapi/domestic-stock/v1/quotations/inquire-index-category-price` | fid_input_iscd(업종코드) | N | Y |

### 1-6. 기타 시세/정보

| # | API명 | tr_id | Method | URL Path | 주요 파라미터 | 과거조회 | 페이징 |
|---|-------|-------|--------|----------|-------------|---------|--------|
| 48 | 종목조건검색 목록 | HHKST03900300 | GET | `/uapi/domestic-stock/v1/quotations/psearch-title` | user_id | N | N |
| 49 | 종목조건검색 결과 | HHKST03900400 | GET | `/uapi/domestic-stock/v1/quotations/psearch-result` | user_id, seq | N | N |
| 50 | 종목기본정보조회 | CTPF1002R | GET | `/uapi/domestic-stock/v1/quotations/search-stock-info` | pdno, prdt_type_cd | N | N |
| 51 | 종목검색정보 | - | GET | `/uapi/domestic-stock/v1/quotations/search-info` | - | N | N |
| 52 | 공매도 일별추이 | FHPST04830000 | GET | `/uapi/domestic-stock/v1/quotations/daily-short-sale` | fid_input_iscd, fid_input_date_1, fid_input_date_2 | **Y** | Y |
| 53 | 신용잔고 | - | GET | `/uapi/domestic-stock/v1/quotations/credit-balance` | fid_input_iscd | N | N |
| 54 | 일자별 신용잔고 | - | GET | `/uapi/domestic-stock/v1/quotations/daily-credit-balance` | fid_input_iscd | **Y** | Y |
| 55 | 회사별 신용 | - | GET | `/uapi/domestic-stock/v1/quotations/credit-by-company` | fid_input_iscd | N | N |
| 56 | 일자별 대차추이 | - | GET | `/uapi/domestic-stock/v1/quotations/daily-loan-trans` | fid_input_iscd | **Y** | Y |
| 57 | 회사별 대주가능 | - | GET | `/uapi/domestic-stock/v1/quotations/lendable-by-company` | fid_input_iscd | N | N |
| 58 | 회사별 매매현황 | - | GET | `/uapi/domestic-stock/v1/quotations/traded-by-company` | fid_input_iscd | N | Y |
| 59 | 괴리율 | - | GET | `/uapi/domestic-stock/v1/quotations/disparity` | fid_input_iscd | N | Y |
| 60 | 체결강도 | - | GET | `/uapi/domestic-stock/v1/quotations/volume-power` | fid_input_iscd | N | Y |
| 61 | 기간별 권리 | - | GET | `/uapi/domestic-stock/v1/quotations/period-rights` | fid_input_iscd | **Y** | Y |
| 62 | 대량거래건수 | - | GET | `/uapi/domestic-stock/v1/quotations/bulk-trans-num` | fid_input_iscd | N | Y |
| 63 | 종합이자율(복리) | - | GET | `/uapi/domestic-stock/v1/quotations/comp-interest` | - | N | N |
| 64 | VI 현황 | - | GET | `/uapi/domestic-stock/v1/quotations/inquire-vi-status` | - | N | Y |
| 65 | 국내 휴장일 | CTCA0903R | GET | `/uapi/domestic-stock/v1/quotations/chk-holiday` | bass_dt, ctx_area_nk(YYYYMMDD) | **Y** | Y |
| 66 | 관심종목 그룹목록 | - | GET | `/uapi/domestic-stock/v1/quotations/intstock-grouplist` | - | N | N |
| 67 | 관심종목 종목리스트 | - | GET | `/uapi/domestic-stock/v1/quotations/intstock-stocklist-by-group` | - | N | N |
| 68 | 관심종목 멀티시세 | - | GET | `/uapi/domestic-stock/v1/quotations/intstock-multprice` | - | N | N |
| 69 | 시간외잔량 | - | GET | `/uapi/domestic-stock/v1/quotations/after-hour-balance` | fid_input_iscd | N | N |
| 70 | 예상지수추이 | - | GET | `/uapi/domestic-stock/v1/quotations/exp-index-trend` | - | N | Y |
| 71 | 예상체결가추이 | - | GET | `/uapi/domestic-stock/v1/quotations/exp-price-trend` | fid_input_iscd | N | Y |
| 72 | 예상종합지수 | - | GET | `/uapi/domestic-stock/v1/quotations/exp-total-index` | - | N | N |
| 73 | 예상매매등락 | - | GET | `/uapi/domestic-stock/v1/quotations/exp-trans-updown` | - | N | Y |
| 74 | 예상장마감가 | - | GET | `/uapi/domestic-stock/v1/quotations/exp-closing-price` | - | N | Y |
| 75 | 호가잔량(KRX) | - | WS/GET | `/uapi/domestic-stock/v1/quotations/asking-price-krx` | fid_input_iscd | N | N |
| 76 | 호가잔량(NXT) | - | WS/GET | `/uapi/domestic-stock/v1/quotations/asking-price-nxt` | fid_input_iscd | N | N |
| 77 | 호가잔량(통합) | - | WS/GET | `/uapi/domestic-stock/v1/quotations/asking-price-total` | fid_input_iscd | N | N |
| 78 | 체결(KRX) | - | WS/GET | `/uapi/domestic-stock/v1/quotations/ccnl-krx` | fid_input_iscd | N | N |
| 79 | 체결(NXT) | - | WS/GET | `/uapi/domestic-stock/v1/quotations/ccnl-nxt` | fid_input_iscd | N | N |
| 80 | 체결(통합) | - | WS/GET | `/uapi/domestic-stock/v1/quotations/ccnl-total` | fid_input_iscd | N | N |
| 81 | 체결통보 | - | WS | (WebSocket) | - | N | N |
| 82 | 예상체결(KRX) | - | GET | `/uapi/domestic-stock/v1/quotations/exp-ccnl-krx` | - | N | N |
| 83 | 예상체결(NXT) | - | GET | `/uapi/domestic-stock/v1/quotations/exp-ccnl-nxt` | - | N | N |
| 84 | 예상체결(통합) | - | GET | `/uapi/domestic-stock/v1/quotations/exp-ccnl-total` | - | N | N |
| 85 | 시장상태(KRX) | - | GET | `/uapi/domestic-stock/v1/quotations/market-status-krx` | - | N | N |
| 86 | 시장상태(NXT) | - | GET | `/uapi/domestic-stock/v1/quotations/market-status-nxt` | - | N | N |
| 87 | 시장상태(통합) | - | GET | `/uapi/domestic-stock/v1/quotations/market-status-total` | - | N | N |
| 88 | 시장운영시간 | - | GET | `/uapi/domestic-stock/v1/quotations/market-time` | - | N | N |
| 89 | 회원사별체결(KRX) | - | GET | `/uapi/domestic-stock/v1/quotations/member-krx` | fid_input_iscd | N | N |
| 90 | 회원사별체결(NXT) | - | GET | `/uapi/domestic-stock/v1/quotations/member-nxt` | fid_input_iscd | N | N |
| 91 | 회원사별체결(통합) | - | GET | `/uapi/domestic-stock/v1/quotations/member-total` | fid_input_iscd | N | N |
| 92 | 회원사일별체결 | - | GET | `/uapi/domestic-stock/v1/quotations/inquire-member-daily` | fid_input_iscd | **Y** | Y |
| 93 | 호가잔량추이 | - | GET | `/uapi/domestic-stock/v1/quotations/quote-balance` | fid_input_iscd | N | Y |
| 94 | 시세자금(MKT자금) | - | GET | `/uapi/domestic-stock/v1/quotations/mktfunds` | - | N | Y |
| 95 | 일별시간대별차트 | - | GET | `/uapi/domestic-stock/v1/quotations/inquire-time-dailychartprice` | fid_input_iscd | **Y** | Y |

### 1-7. 실시간 (WebSocket)

| # | API명 | tr_id | Protocol | 설명 |
|---|-------|-------|----------|------|
| 96 | 실시간호가(통합) | H0UNASP0 | WebSocket | 국내주식 실시간호가 (10호가) |
| 97 | 실시간체결(통합) | H0UNCNT0 | WebSocket | 국내주식 실시간체결가 |
| 98 | 실시간체결통보 | H0UNCNC0 | WebSocket | 주문 체결 통보 |

---

## 2. 국내주식 주문/계좌 (Trading)

| # | API명 | tr_id (실전) | tr_id (모의) | Method | URL Path | 주요 파라미터 | 과거조회 | 페이징 |
|---|-------|-------------|-------------|--------|----------|-------------|---------|--------|
| 1 | 현금매수주문 | TTTC0012U | VTTC0012U | POST | `/uapi/domestic-stock/v1/trading/order-cash` | CANO, PDNO, ORD_DVSN, ORD_QTY, ORD_UNPR | N | N |
| 2 | 현금매도주문 | TTTC0011U | VTTC0011U | POST | `/uapi/domestic-stock/v1/trading/order-cash` | CANO, PDNO, ORD_DVSN, ORD_QTY, ORD_UNPR | N | N |
| 3 | 정정취소주문 | TTTC0013U | VTTC0013U | POST | `/uapi/domestic-stock/v1/trading/order-rvsecncl` | CANO, ORGN_ODNO, RVSE_CNCL_DVSN_CD, ORD_QTY | N | N |
| 4 | 신용매수주문 | TTTC0052U | - | POST | `/uapi/domestic-stock/v1/trading/order-credit` | CANO, PDNO, ORD_QTY, ORD_UNPR | N | N |
| 5 | 신용매도주문 | TTTC0051U | - | POST | `/uapi/domestic-stock/v1/trading/order-credit` | CANO, PDNO, ORD_QTY, ORD_UNPR | N | N |
| 6 | 예약주문 | CTSC0008U | - | POST | `/uapi/domestic-stock/v1/trading/order-resv` | CANO, PDNO, ORD_QTY, ORD_UNPR, 예약종료일 | N | N |
| 7 | 예약주문 정정취소 | - | - | POST | `/uapi/domestic-stock/v1/trading/order-resv-rvsecncl` | CANO, ORGN_ODNO | N | N |
| 8 | 예약주문 체결내역 | - | - | GET | `/uapi/domestic-stock/v1/trading/order-resv-ccnl` | CANO, 조회기간 | **Y** | Y |
| 9 | 잔고조회 | TTTC8434R | VTTC8434R | GET | `/uapi/domestic-stock/v1/trading/inquire-balance` | CANO, ACNT_PRDT_CD, AFHR_FLPR_YN | N | Y(50건/20건) |
| 10 | 체결기준잔고(실현손익) | TTTC8494R | - | GET | `/uapi/domestic-stock/v1/trading/inquire-balance-rlz-pl` | CANO, ACNT_PRDT_CD | N | Y |
| 11 | 일별주문체결내역 | TTTC0081R/CTSC9215R | VTTC0081R/VTSC9215R | GET | `/uapi/domestic-stock/v1/trading/inquire-daily-ccld` | CANO, INQR_STRT_DT, INQR_END_DT, SLL_BUY_DVSN_CD | **Y** | Y(100건/15건) |
| 12 | 매수가능조회 | TTTC8908R | VTTC8908R | GET | `/uapi/domestic-stock/v1/trading/inquire-psbl-order` | CANO, PDNO, ORD_UNPR | N | N |
| 13 | 매도가능수량조회 | TTTC8408R | - | GET | `/uapi/domestic-stock/v1/trading/inquire-psbl-sell` | CANO, PDNO | N | N |
| 14 | 정정취소가능조회 | - | - | GET | `/uapi/domestic-stock/v1/trading/inquire-psbl-rvsecncl` | CANO | N | Y |
| 15 | 신용매수가능조회 | - | - | GET | `/uapi/domestic-stock/v1/trading/inquire-credit-psamount` | CANO, PDNO | N | N |
| 16 | 기간별손익조회 | - | - | GET | `/uapi/domestic-stock/v1/trading/inquire-period-profit` | CANO, 기간 | **Y** | Y |
| 17 | 기간별매매손익조회 | - | - | GET | `/uapi/domestic-stock/v1/trading/inquire-period-trade-profit` | CANO, 기간 | **Y** | Y |
| 18 | 계좌잔고조회 | - | - | GET | `/uapi/domestic-stock/v1/trading/inquire-account-balance` | CANO | N | Y |
| 19 | 통합증거금조회 | - | - | GET | `/uapi/domestic-stock/v1/trading/intgr-margin` | CANO | N | N |
| 20 | 매매비중(금액별) | - | - | GET | `/uapi/domestic-stock/v1/trading/tradprt-byamt` | - | N | Y |

### 연금저축 계좌

| # | API명 | tr_id | Method | URL Path |
|---|-------|-------|--------|----------|
| 21 | 연금잔고조회 | - | GET | `/uapi/domestic-stock/v1/trading/pension-inquire-balance` |
| 22 | 연금체결내역 | - | GET | `/uapi/domestic-stock/v1/trading/pension-inquire-daily-ccld` |
| 23 | 연금예수금조회 | - | GET | `/uapi/domestic-stock/v1/trading/pension-inquire-deposit` |
| 24 | 연금현재잔고 | - | GET | `/uapi/domestic-stock/v1/trading/pension-inquire-present-balance` |
| 25 | 연금매수가능조회 | - | GET | `/uapi/domestic-stock/v1/trading/pension-inquire-psbl-order` |

---

## 3. 국내주식 재무 (Finance)

| # | API명 | tr_id | Method | URL Path | 주요 파라미터 | 과거조회 | 페이징 |
|---|-------|-------|--------|----------|-------------|---------|--------|
| 1 | 손익계산서 | FHKST66430200 | GET | `/uapi/domestic-stock/v1/finance/income-statement` | fid_input_iscd, fid_div_cls_code(0=연간/1=분기) | N | Y |
| 2 | 대차대조표 | FHKST66430100 | GET | `/uapi/domestic-stock/v1/finance/balance-sheet` | fid_input_iscd, fid_div_cls_code | N | Y |
| 3 | 재무비율 | FHKST66430300 | GET | `/uapi/domestic-stock/v1/finance/financial-ratio` | fid_input_iscd, fid_div_cls_code | N | Y |
| 4 | 수익성비율 | FHKST66430400 | GET | `/uapi/domestic-stock/v1/finance/profit-ratio` | fid_input_iscd, fid_div_cls_code | N | Y |
| 5 | 기타주요비율 | FHKST66430500 | GET | `/uapi/domestic-stock/v1/finance/other-major-ratios` | fid_input_iscd, fid_div_cls_code | N | Y |
| 6 | 안정성비율 | FHKST66430600 | GET | `/uapi/domestic-stock/v1/finance/stability-ratio` | fid_input_iscd, fid_div_cls_code | N | Y |
| 7 | 성장성비율 | FHKST66430800 | GET | `/uapi/domestic-stock/v1/finance/growth-ratio` | fid_input_iscd, fid_div_cls_code | N | Y |

---

## 4. 국내주식 순위분석 (Ranking)

| # | API명 | tr_id | Method | URL Path | 주요 파라미터 | 과거조회 | 페이징 |
|---|-------|-------|--------|----------|-------------|---------|--------|
| 1 | 거래량순위 | FHPST01710000 | GET | `/uapi/domestic-stock/v1/quotations/volume-rank` | fid_cond_mrkt_div_code, fid_blng_cls_code, fid_input_price_1/2 | N | Y |
| 2 | 시가총액순위 | FHPST01740000 | GET | `/uapi/domestic-stock/v1/ranking/market-cap` | fid_input_iscd, fid_div_cls_code | N | Y |
| 3 | 등락률순위 | FHPST01700000 | GET | `/uapi/domestic-stock/v1/ranking/fluctuation` | fid_rsfl_rate1/2, fid_rank_sort_cls_code | N | Y |
| 4 | 공매도상위종목 | FHPST04820000 | GET | `/uapi/domestic-stock/v1/ranking/short-sale` | fid_period_div_code(D/M), fid_input_cnt_1 | **Y** | Y |
| 5 | 재무비율순위 | FHPST01750000 | GET | `/uapi/domestic-stock/v1/ranking/finance-ratio` | fid_input_iscd | N | Y |
| 6 | 배당률순위 | HHKDB13470100 | GET | `/uapi/domestic-stock/v1/ranking/dividend-rate` | fid_input_iscd, fid_input_date_1/2 | **Y** | Y |
| 7 | 상한가/하한가 포착 | - | GET | `/uapi/domestic-stock/v1/quotations/capture-uplowprice` | - | N | Y |
| 8 | 신고/신저 근접종목 | - | GET | `/uapi/domestic-stock/v1/quotations/near-new-highlow` | - | N | Y |
| 9 | 시가대비비율 | - | GET | `/uapi/domestic-stock/v1/quotations/pbar-tratio` | - | N | Y |
| 10 | 우선주 괴리율 | - | GET | `/uapi/domestic-stock/v1/quotations/prefer-disparate-ratio` | - | N | Y |
| 11 | HTS 관심종목 상위 | - | GET | `/uapi/domestic-stock/v1/quotations/hts-top-view` | - | N | Y |
| 12 | 최다관심종목 | - | GET | `/uapi/domestic-stock/v1/quotations/top-interest-stock` | - | N | Y |
| 13 | 수익자산지표순위 | - | GET | `/uapi/domestic-stock/v1/quotations/profit-asset-index` | - | N | Y |
| 14 | 시장가치 | - | GET | `/uapi/domestic-stock/v1/quotations/market-value` | - | N | Y |
| 15 | 추정실적(컨센서스) | - | GET | `/uapi/domestic-stock/v1/quotations/estimate-perform` | fid_input_iscd | N | N |
| 16 | 투자의견 | - | GET | `/uapi/domestic-stock/v1/quotations/invest-opinion` | fid_input_iscd | N | Y |
| 17 | 증권사별투자의견 | - | GET | `/uapi/domestic-stock/v1/quotations/invest-opbysec` | fid_input_iscd | N | Y |

---

## 5. 국내주식 종목정보 (KSD Info)

| # | API명 | tr_id | Method | URL Path | 과거조회 |
|---|-------|-------|--------|----------|---------|
| 1 | 상장정보 | - | GET | `/uapi/domestic-stock/v1/quotations/ksdinfo-list-info` | Y |
| 2 | 배당정보 | - | GET | `/uapi/domestic-stock/v1/quotations/ksdinfo-dividend` | Y |
| 3 | 유상증자 | - | GET | `/uapi/domestic-stock/v1/quotations/ksdinfo-paidin-capin` | Y |
| 4 | 무상증자 | - | GET | `/uapi/domestic-stock/v1/quotations/ksdinfo-bonus-issue` | Y |
| 5 | 감자 | - | GET | `/uapi/domestic-stock/v1/quotations/ksdinfo-cap-dcrs` | Y |
| 6 | 실권/실격 | - | GET | `/uapi/domestic-stock/v1/quotations/ksdinfo-forfeit` | Y |
| 7 | 의무보유 | - | GET | `/uapi/domestic-stock/v1/quotations/ksdinfo-mand-deposit` | Y |
| 8 | 합병/분할 | - | GET | `/uapi/domestic-stock/v1/quotations/ksdinfo-merger-split` | Y |
| 9 | 공모 | - | GET | `/uapi/domestic-stock/v1/quotations/ksdinfo-pub-offer` | Y |
| 10 | 매수청구 | - | GET | `/uapi/domestic-stock/v1/quotations/ksdinfo-purreq` | Y |
| 11 | 주식병합 | - | GET | `/uapi/domestic-stock/v1/quotations/ksdinfo-rev-split` | Y |
| 12 | 주주총회 | - | GET | `/uapi/domestic-stock/v1/quotations/ksdinfo-sharehld-meet` | Y |

---

## 6. 해외주식 시세 (Overseas Price/Quotations)

| # | API명 | tr_id | Method | URL Path | 주요 파라미터 | 과거조회 | 페이징 |
|---|-------|-------|--------|----------|-------------|---------|--------|
| 1 | 해외주식 현재체결가 | HHDFS00000300 | GET | `/uapi/overseas-price/v1/quotations/price` | EXCD(거래소코드), SYMB(종목코드) | N | N |
| 2 | 해외주식 현재가상세 | HHDFS76200200 | GET | `/uapi/overseas-price/v1/quotations/price-detail` | EXCD, SYMB | N | N |
| 3 | 해외주식 기간별시세(일/주/월) | HHDFS76240000 | GET | `/uapi/overseas-price/v1/quotations/dailyprice` | EXCD, SYMB, GUBN(D/W/M), BYMD | **Y** | Y |
| 4 | 해외주식 분봉차트 | HHDFS76950200 | GET | `/uapi/overseas-price/v1/quotations/inquire-time-itemchartprice` | EXCD, SYMB, NMIN(분단위), PINC(당일/연속) | N | Y |
| 5 | 해외주식 호가 | HHDFS76200100 | GET | `/uapi/overseas-price/v1/quotations/inquire-asking-price` | EXCD, SYMB | N | Y |
| 6 | 해외주식 조건검색 | HHDFS76410000 | GET | `/uapi/overseas-price/v1/quotations/inquire-search` | EXCD, 가격범위, PER, EPS, 시총 등 | N | Y |
| 7 | 해외주식 등락률 | - | GET | `/uapi/overseas-price/v1/quotations/updown-rate` | EXCD | N | Y |
| 8 | 해외주식 가격변동 | - | GET | `/uapi/overseas-price/v1/quotations/price-fluct` | EXCD, SYMB | **Y** | Y |
| 9 | 해외주식 지수기간차트 | FHKST03030100 | GET | `/uapi/overseas-price/v1/quotations/inquire-daily-chartprice` | fid_input_iscd, fid_input_date_1/2, fid_period_div_code | **Y** | Y |
| 10 | 해외주식 지수분봉차트 | - | GET | `/uapi/overseas-price/v1/quotations/inquire-time-indexchartprice` | fid_input_iscd | N | Y |
| 11 | 해외주식 뉴스제목 | - | GET | `/uapi/overseas-price/v1/quotations/news-title` | EXCD, SYMB | N | Y |
| 12 | 해외주식 증권사뉴스 | - | GET | `/uapi/overseas-price/v1/quotations/brknews-title` | EXCD, SYMB | N | Y |
| 13 | 해외주식 시가총액 | - | GET | `/uapi/overseas-price/v1/quotations/market-cap` | EXCD | N | Y |
| 14 | 해외주식 신고/신저 | - | GET | `/uapi/overseas-price/v1/quotations/new-highlow` | EXCD | N | Y |
| 15 | 해외주식 거래량급증 | - | GET | `/uapi/overseas-price/v1/quotations/volume-surge` | EXCD | N | Y |
| 16 | 해외주식 거래대금 | - | GET | `/uapi/overseas-price/v1/quotations/trade-pbmn` | EXCD | N | Y |
| 17 | 해외주식 거래량 | - | GET | `/uapi/overseas-price/v1/quotations/trade-vol` | EXCD | N | Y |
| 18 | 해외주식 매출성장률 | - | GET | `/uapi/overseas-price/v1/quotations/trade-growth` | EXCD | N | Y |
| 19 | 해외주식 회전율 | - | GET | `/uapi/overseas-price/v1/quotations/trade-turnover` | EXCD | N | Y |
| 20 | 해외주식 체결강도 | - | GET | `/uapi/overseas-price/v1/quotations/volume-power` | EXCD, SYMB | N | Y |
| 21 | 해외주식 업종시세 | - | GET | `/uapi/overseas-price/v1/quotations/industry-price` | EXCD | N | Y |
| 22 | 해외주식 업종테마 | - | GET | `/uapi/overseas-price/v1/quotations/industry-theme` | EXCD | N | Y |
| 23 | 해외주식 종목정보 | - | GET | `/uapi/overseas-price/v1/quotations/search-info` | EXCD, SYMB | N | N |
| 24 | 해외주식 기간별 권리 | - | GET | `/uapi/overseas-price/v1/quotations/period-rights` | EXCD, SYMB | **Y** | Y |
| 25 | 해외주식 ICE 권리 | - | GET | `/uapi/overseas-price/v1/quotations/rights-by-ice` | EXCD, SYMB | N | Y |
| 26 | 해외국가 휴장일 | - | GET | `/uapi/overseas-price/v1/quotations/countries-holiday` | 국가코드 | **Y** | Y |
| 27 | 해외주식 지연호가(아시아) | - | GET | `/uapi/overseas-price/v1/quotations/delayed-asking-price-asia` | EXCD, SYMB | N | N |
| 28 | 해외주식 지연체결 | - | GET | `/uapi/overseas-price/v1/quotations/delayed-ccnl` | EXCD, SYMB | N | N |
| 29 | 해외주식 외국인 증거금 | - | GET | `/uapi/overseas-price/v1/quotations/foreign-margin` | EXCD, SYMB | N | N |
| 30 | 해외주식 대차가능종목 | - | GET | `/uapi/overseas-price/v1/quotations/colable-by-company` | EXCD | N | Y |
| 31 | 해외주식 체결 | - | GET | `/uapi/overseas-price/v1/quotations/quot-inquire-ccnl` | EXCD, SYMB | N | Y |

### 해외주식 실시간 (WebSocket)

| # | API명 | tr_id | Protocol |
|---|-------|-------|----------|
| 32 | 해외주식 실시간호가 | HDFSASP0 | WebSocket |
| 33 | 해외주식 실시간체결 | HDFSCNT0 | WebSocket |
| 34 | 해외주식 체결통보 | H0GSCNI0/H0GSCNI9 | WebSocket |

---

## 7. 해외주식 주문/계좌 (Overseas Trading)

| # | API명 | tr_id (실전) | Method | URL Path | 주요 파라미터 | 과거조회 | 페이징 |
|---|-------|-------------|--------|----------|-------------|---------|--------|
| 1 | 해외주식주문 (미국매수) | TTTT1002U | POST | `/uapi/overseas-stock/v1/trading/order` | OVRS_EXCG_CD, PDNO, ORD_QTY, OVRS_ORD_UNPR, ORD_DVSN | N | N |
| 2 | 해외주식주문 (미국매도) | TTTT1006U | POST | `/uapi/overseas-stock/v1/trading/order` | 상동 | N | N |
| 3 | 해외주식주문 (홍콩매수) | TTTS1002U | POST | `/uapi/overseas-stock/v1/trading/order` | 상동 | N | N |
| 4 | 해외주식주문 (홍콩매도) | TTTS1001U | POST | `/uapi/overseas-stock/v1/trading/order` | 상동 | N | N |
| 5 | 해외주식주문 (상해매수) | TTTS0202U | POST | `/uapi/overseas-stock/v1/trading/order` | 상동 | N | N |
| 6 | 해외주식주문 (상해매도) | TTTS1005U | POST | `/uapi/overseas-stock/v1/trading/order` | 상동 | N | N |
| 7 | 해외주식주문 (심천매수) | TTTS0305U | POST | `/uapi/overseas-stock/v1/trading/order` | 상동 | N | N |
| 8 | 해외주식주문 (심천매도) | TTTS0304U | POST | `/uapi/overseas-stock/v1/trading/order` | 상동 | N | N |
| 9 | 해외주식주문 (일본매수) | TTTS0308U | POST | `/uapi/overseas-stock/v1/trading/order` | 상동 | N | N |
| 10 | 해외주식주문 (일본매도) | TTTS0307U | POST | `/uapi/overseas-stock/v1/trading/order` | 상동 | N | N |
| 11 | 해외주식주문 (베트남매수) | TTTS0311U | POST | `/uapi/overseas-stock/v1/trading/order` | 상동 | N | N |
| 12 | 해외주식주문 (베트남매도) | TTTS0310U | POST | `/uapi/overseas-stock/v1/trading/order` | 상동 | N | N |
| 13 | 해외주식 정정취소 | TTTT1004U | POST | `/uapi/overseas-stock/v1/trading/order-rvsecncl` | ORGN_ODNO, RVSE_CNCL_DVSN_CD | N | N |
| 14 | 해외주식 주간주문 | - | POST | `/uapi/overseas-stock/v1/trading/daytime-order` | PDNO, ORD_QTY, OVRS_ORD_UNPR | N | N |
| 15 | 해외주식 주간정정취소 | - | POST | `/uapi/overseas-stock/v1/trading/daytime-order-rvsecncl` | ORGN_ODNO | N | N |
| 16 | 해외주식 예약주문 | - | POST | `/uapi/overseas-stock/v1/trading/order-resv` | PDNO, ORD_QTY | N | N |
| 17 | 해외주식 예약주문 목록 | - | GET | `/uapi/overseas-stock/v1/trading/order-resv-list` | CANO | N | Y |
| 18 | 해외주식 예약주문 체결 | - | GET | `/uapi/overseas-stock/v1/trading/order-resv-ccnl` | CANO | **Y** | Y |
| 19 | 해외주식 잔고조회 | TTTS3012R | GET | `/uapi/overseas-stock/v1/trading/inquire-balance` | CANO, OVRS_EXCG_CD, TR_CRCY_CD | N | Y |
| 20 | 해외주식 체결내역 | TTTS3035R | GET | `/uapi/overseas-stock/v1/trading/inquire-ccnl` | CANO, 기간 | **Y** | Y |
| 21 | 해외주식 미체결내역 | - | GET | `/uapi/overseas-stock/v1/trading/inquire-nccs` | CANO | N | Y |
| 22 | 해외주식 매수가능금액 | TTTS3007R | GET | `/uapi/overseas-stock/v1/trading/inquire-psamount` | CANO, PDNO, OVRS_ORD_UNPR | N | N |
| 23 | 해외주식 기간손익조회 | TTTS3039R | GET | `/uapi/overseas-stock/v1/trading/inquire-period-profit` | CANO, 기간 | **Y** | Y |
| 24 | 해외주식 기간거래내역 | - | GET | `/uapi/overseas-stock/v1/trading/inquire-period-trans` | CANO, 기간 | **Y** | Y |
| 25 | 해외주식 현재잔고 | - | GET | `/uapi/overseas-stock/v1/trading/inquire-present-balance` | CANO | N | Y |
| 26 | 해외주식 결제기준잔고 | - | GET | `/uapi/overseas-stock/v1/trading/inquire-paymt-stdr-balance` | CANO | N | Y |
| 27 | 해외주식 알고주문번호 | - | GET | `/uapi/overseas-stock/v1/trading/algo-ordno` | CANO | N | N |
| 28 | 해외주식 알고체결내역 | - | GET | `/uapi/overseas-stock/v1/trading/inquire-algo-ccnl` | CANO | **Y** | Y |

---

## 8. ETF/ETN

| # | API명 | tr_id | Method | URL Path | 주요 파라미터 | 과거조회 | 페이징 |
|---|-------|-------|--------|----------|-------------|---------|--------|
| 1 | ETF/ETN 현재가 | FHPST02400000 | GET | `/uapi/etfetn/v1/quotations/inquire-price` | FID_COND_MRKT_DIV_CODE, FID_INPUT_ISCD | N | N |
| 2 | NAV 비교추이(종목) | FHPST02440000 | GET | `/uapi/etfetn/v1/quotations/nav-comparison-trend` | FID_INPUT_ISCD | N | Y |
| 3 | NAV 비교추이(일별) | - | GET | `/uapi/etfetn/v1/quotations/nav-comparison-daily-trend` | FID_INPUT_ISCD | **Y** | Y |
| 4 | NAV 비교추이(시간별) | - | GET | `/uapi/etfetn/v1/quotations/nav-comparison-time-trend` | FID_INPUT_ISCD | N | Y |
| 5 | 구성종목시세 | - | GET | `/uapi/etfetn/v1/quotations/inquire-component-stock-price` | FID_INPUT_ISCD | N | Y |
| 6 | ETF NAV추이 (실시간) | H0STNAV0 | WebSocket | (WebSocket) | 종목코드 | N | N |

---

## 9. ELW

| # | API명 | tr_id | Method | URL Path | 과거조회 | 페이징 |
|---|-------|-------|--------|----------|---------|--------|
| 1 | ELW 현재가 | - | GET | `inquire-elw-price` (1-1 #12 참조) | N | Y |
| 2 | ELW 호가 | - | GET | `/uapi/domestic-stock/v1/quotations/elw-asking-price` | N | N |
| 3 | ELW 체결 | - | GET | `/uapi/domestic-stock/v1/quotations/elw-ccnl` | N | N |
| 4 | ELW 예상체결 | - | GET | `/uapi/domestic-stock/v1/quotations/elw-exp-ccnl` | N | N |
| 5 | ELW 신규상장 | - | GET | `/uapi/domestic-stock/v1/quotations/elw-newly-listed` | N | Y |
| 6 | ELW 거래량순위 | - | GET | `/uapi/domestic-stock/v1/quotations/elw-volume-rank` | N | Y |
| 7 | ELW 등락률 | - | GET | `/uapi/domestic-stock/v1/quotations/elw-updown-rate` | N | Y |
| 8 | ELW 민감도 | - | GET | `/uapi/domestic-stock/v1/quotations/elw-sensitivity` | N | Y |
| 9 | ELW 민감도추이(체결) | - | GET | `/uapi/domestic-stock/v1/quotations/elw-sensitivity-trend-ccnl` | N | Y |
| 10 | ELW 민감도추이(일별) | - | GET | `/uapi/domestic-stock/v1/quotations/elw-sensitivity-trend-daily` | Y | Y |
| 11 | ELW 조건검색 | - | GET | `/uapi/domestic-stock/v1/quotations/elw-cond-search` | N | Y |
| 12 | ELW 기초자산목록 | - | GET | `/uapi/domestic-stock/v1/quotations/elw-udrl-asset-list` | N | Y |
| 13 | ELW 기초자산시세 | - | GET | `/uapi/domestic-stock/v1/quotations/elw-udrl-asset-price` | N | N |
| 14 | ELW 지표 | - | GET | `/uapi/domestic-stock/v1/quotations/elw-indicator` | N | N |
| 15 | ELW 지표추이(체결) | - | GET | `/uapi/domestic-stock/v1/quotations/elw-indicator-trend-ccnl` | N | Y |
| 16 | ELW 지표추이(일별) | - | GET | `/uapi/domestic-stock/v1/quotations/elw-indicator-trend-daily` | Y | Y |
| 17 | ELW 지표추이(분별) | - | GET | `/uapi/domestic-stock/v1/quotations/elw-indicator-trend-minute` | N | Y |
| 18 | ELW 변동성추이(체결) | - | GET | `/uapi/domestic-stock/v1/quotations/elw-volatility-trend-ccnl` | N | Y |
| 19 | ELW 변동성추이(일별) | - | GET | `/uapi/domestic-stock/v1/quotations/elw-volatility-trend-daily` | Y | Y |
| 20 | ELW 변동성추이(분별) | - | GET | `/uapi/domestic-stock/v1/quotations/elw-volatility-trend-minute` | N | Y |
| 21 | ELW 변동성추이(틱별) | - | GET | `/uapi/domestic-stock/v1/quotations/elw-volatility-trend-tick` | N | Y |
| 22 | ELW 만기종목 | - | GET | `/uapi/domestic-stock/v1/quotations/elw-expiration-stocks` | N | Y |
| 23 | ELW 급변동 | - | GET | `/uapi/domestic-stock/v1/quotations/elw-quick-change` | N | Y |
| 24 | ELW LP매매동향 | - | GET | `/uapi/domestic-stock/v1/quotations/elw-lp-trade-trend` | N | Y |
| 25 | ELW 종목비교 | - | GET | `/uapi/domestic-stock/v1/quotations/elw-compare-stocks` | N | Y |

---

## 10. 국내 선물옵션 (Domestic Futures/Options)

### 10-1. 주문/계좌

| # | API명 | tr_id (실전) | Method | URL Path | 과거조회 | 페이징 |
|---|-------|-------------|--------|----------|---------|--------|
| 1 | 선물옵션 주문(주간) | TTTO1101U | POST | `/uapi/domestic-futureoption/v1/trading/order` | N | N |
| 2 | 선물옵션 주문(야간) | STTN1101U | POST | `/uapi/domestic-futureoption/v1/trading/order` | N | N |
| 3 | 선물옵션 정정취소 | - | POST | `/uapi/domestic-futureoption/v1/trading/order-rvsecncl` | N | N |
| 4 | 선물옵션 잔고 | CTFO6118R | GET | `/uapi/domestic-futureoption/v1/trading/inquire-balance` | N | Y(20건) |
| 5 | 선물옵션 잔고(결제손익) | - | GET | `/uapi/domestic-futureoption/v1/trading/inquire-balance-settlement-pl` | N | Y |
| 6 | 선물옵션 잔고(평가손익) | - | GET | `/uapi/domestic-futureoption/v1/trading/inquire-balance-valuation-pl` | N | Y |
| 7 | 선물옵션 체결내역 | - | GET | `/uapi/domestic-futureoption/v1/trading/inquire-ccnl` | Y | Y |
| 8 | 선물옵션 체결내역(시간별) | - | GET | `/uapi/domestic-futureoption/v1/trading/inquire-ccnl-bstime` | Y | Y |
| 9 | 선물옵션 예수금 | - | GET | `/uapi/domestic-futureoption/v1/trading/inquire-deposit` | N | N |
| 10 | 선물옵션 주문가능 | - | GET | `/uapi/domestic-futureoption/v1/trading/inquire-psbl-order` | N | N |
| 11 | 선물옵션 일별수수료 | - | GET | `/uapi/domestic-futureoption/v1/trading/inquire-daily-amount-fee` | Y | Y |
| 12 | 야간선물옵션 잔고 | - | GET | `/uapi/domestic-futureoption/v1/trading/inquire-ngt-balance` | N | Y |
| 13 | 야간선물옵션 체결 | - | GET | `/uapi/domestic-futureoption/v1/trading/inquire-ngt-ccnl` | Y | Y |
| 14 | 야간선물옵션 주문가능 | - | GET | `/uapi/domestic-futureoption/v1/trading/inquire-psbl-ngt-order` | N | N |
| 15 | 야간증거금상세 | - | GET | `/uapi/domestic-futureoption/v1/trading/ngt-margin-detail` | N | N |

### 10-2. 시세

| # | API명 | tr_id | Method | URL Path | 과거조회 | 페이징 |
|---|-------|-------|--------|----------|---------|--------|
| 16 | 선물옵션 현재가 | FHMIF10000000 | GET | `/uapi/domestic-futureoption/v1/quotations/inquire-price` | N | N |
| 17 | 선물옵션 호가 | - | GET | `/uapi/domestic-futureoption/v1/quotations/inquire-asking-price` | N | N |
| 18 | 선물옵션 기간별시세 | - | GET | `/uapi/domestic-futureoption/v1/quotations/inquire-daily-fuopchartprice` | Y | Y |
| 19 | 선물옵션 분봉차트 | - | GET | `/uapi/domestic-futureoption/v1/quotations/inquire-time-fuopchartprice` | N | Y |
| 20 | 선물 예상체결 | - | GET | `/uapi/domestic-futureoption/v1/quotations/futures-exp-ccnl` | N | N |
| 21 | 옵션 예상체결 | - | GET | `/uapi/domestic-futureoption/v1/quotations/option-exp-ccnl` | N | N |
| 22 | 예상체결가추이(선물옵션) | - | GET | `/uapi/domestic-futureoption/v1/quotations/exp-price-trend` | N | Y |
| 23 | 전광판(선물) | - | GET | `/uapi/domestic-futureoption/v1/quotations/display-board-futures` | N | N |
| 24 | 전광판(콜풋) | - | GET | `/uapi/domestic-futureoption/v1/quotations/display-board-callput` | N | N |
| 25 | 전광판(옵션행사가목록) | - | GET | `/uapi/domestic-futureoption/v1/quotations/display-board-option-list` | N | N |
| 26 | 전광판(상위) | - | GET | `/uapi/domestic-futureoption/v1/quotations/display-board-top` | N | N |
| 27 | 개별옵션 호가 | - | GET | `/uapi/domestic-futureoption/v1/quotations/stock-option-asking-price` | N | N |
| 28 | 개별옵션 체결 | - | GET | `/uapi/domestic-futureoption/v1/quotations/stock-option-ccnl` | N | N |
| 29 | 체결통보(선물옵션) | - | WS | (WebSocket) | N | N |

### 선물옵션 실시간 (WebSocket)

| # | API명 | tr_id | Protocol |
|---|-------|-------|----------|
| 30 | 지수선물 실시간체결 | - | WebSocket |
| 31 | 지수선물 실시간호가 | - | WebSocket |
| 32 | 지수옵션 실시간체결 | - | WebSocket |
| 33 | 지수옵션 실시간호가 | - | WebSocket |
| 34 | 주식선물 실시간체결 | - | WebSocket |
| 35 | 주식선물 실시간호가 | - | WebSocket |
| 36 | 상품선물 실시간체결 | - | WebSocket |
| 37 | 상품선물 실시간호가 | - | WebSocket |
| 38 | KRX 야간선물 호가 | - | WebSocket |
| 39 | KRX 야간선물 체결 | - | WebSocket |
| 40 | KRX 야간선물 체결통보 | - | WebSocket |
| 41 | KRX 야간옵션 호가 | - | WebSocket |
| 42 | KRX 야간옵션 체결 | - | WebSocket |
| 43 | KRX 야간옵션 예상체결 | - | WebSocket |
| 44 | KRX 야간옵션 통보 | - | WebSocket |

---

## 11. 해외 선물옵션 (Overseas Futures/Options)

### 11-1. 주문/계좌

| # | API명 | tr_id | Method | URL Path | 과거조회 | 페이징 |
|---|-------|-------|--------|----------|---------|--------|
| 1 | 해외선물옵션 주문 | OTFM3001U | POST | `/uapi/overseas-futureoption/v1/trading/order` | N | N |
| 2 | 해외선물옵션 정정취소 | - | POST | `/uapi/overseas-futureoption/v1/trading/order-rvsecncl` | N | N |
| 3 | 해외선물옵션 체결내역 | - | GET | `/uapi/overseas-futureoption/v1/trading/inquire-ccld` | Y | Y |
| 4 | 해외선물옵션 일별체결 | - | GET | `/uapi/overseas-futureoption/v1/trading/inquire-daily-ccld` | Y | Y |
| 5 | 해외선물옵션 일별주문 | - | GET | `/uapi/overseas-futureoption/v1/trading/inquire-daily-order` | Y | Y |
| 6 | 해외선물옵션 예수금 | - | GET | `/uapi/overseas-futureoption/v1/trading/inquire-deposit` | N | N |
| 7 | 해외선물옵션 주문가능 | - | GET | `/uapi/overseas-futureoption/v1/trading/inquire-psamount` | N | N |
| 8 | 해외선물옵션 미결제 | - | GET | `/uapi/overseas-futureoption/v1/trading/inquire-unpd` | N | Y |
| 9 | 해외선물옵션 기간체결 | - | GET | `/uapi/overseas-futureoption/v1/trading/inquire-period-ccld` | Y | Y |
| 10 | 해외선물옵션 기간거래 | - | GET | `/uapi/overseas-futureoption/v1/trading/inquire-period-trans` | Y | Y |
| 11 | 해외선물옵션 증거금상세 | - | GET | `/uapi/overseas-futureoption/v1/trading/margin-detail` | N | N |
| 12 | 해외선물옵션 미결제추이 | - | GET | `/uapi/overseas-futureoption/v1/trading/investor-unpd-trend` | Y | Y |
| 13 | 해외선물옵션 체결통보 | - | WS | (WebSocket) | N | N |
| 14 | 해외선물옵션 주문통보 | - | WS | (WebSocket) | N | N |

### 11-2. 시세

| # | API명 | tr_id | Method | URL Path | 과거조회 | 페이징 |
|---|-------|-------|--------|----------|---------|--------|
| 15 | 해외선물 현재가 | - | GET | `/uapi/overseas-futureoption/v1/quotations/inquire-price` | N | N |
| 16 | 해외선물 호가 | - | GET | `/uapi/overseas-futureoption/v1/quotations/inquire-asking-price` | N | N |
| 17 | 해외선물 기간차트 | - | GET | `/uapi/overseas-futureoption/v1/quotations/inquire-time-futurechartprice` | Y | Y |
| 18 | 해외선물 체결(틱) | - | GET | `/uapi/overseas-futureoption/v1/quotations/tick-ccnl` | N | Y |
| 19 | 해외선물 일별체결 | - | GET | `/uapi/overseas-futureoption/v1/quotations/daily-ccnl` | Y | Y |
| 20 | 해외선물 주별체결 | - | GET | `/uapi/overseas-futureoption/v1/quotations/weekly-ccnl` | Y | Y |
| 21 | 해외선물 월별체결 | - | GET | `/uapi/overseas-futureoption/v1/quotations/monthly-ccnl` | Y | Y |
| 22 | 해외선물 체결 | - | GET | `/uapi/overseas-futureoption/v1/quotations/ccnl` | N | Y |
| 23 | 해외선물 호가 (WS) | - | GET | `/uapi/overseas-futureoption/v1/quotations/asking-price` | N | N |
| 24 | 해외선물 체결통보(시세) | - | GET | `/uapi/overseas-futureoption/v1/quotations/ccnl-notice` | N | N |
| 25 | 해외선물 종목상세 | - | GET | `/uapi/overseas-futureoption/v1/quotations/stock-detail` | N | N |
| 26 | 해외선물 종목검색 | - | GET | `/uapi/overseas-futureoption/v1/quotations/search-contract-detail` | N | Y |
| 27 | 해외선물 장운영시간 | - | GET | `/uapi/overseas-futureoption/v1/quotations/market-time` | N | N |
| 28 | 해외옵션 현재가 | - | GET | `/uapi/overseas-futureoption/v1/quotations/opt-price` | N | N |
| 29 | 해외옵션 호가 | - | GET | `/uapi/overseas-futureoption/v1/quotations/opt-asking-price` | N | N |
| 30 | 해외옵션 상세 | - | GET | `/uapi/overseas-futureoption/v1/quotations/opt-detail` | N | N |
| 31 | 해외옵션 검색 | - | GET | `/uapi/overseas-futureoption/v1/quotations/search-opt-detail` | N | Y |
| 32 | 해외옵션 기간차트 | - | GET | `/uapi/overseas-futureoption/v1/quotations/inquire-time-optchartprice` | Y | Y |
| 33 | 해외옵션 틱체결 | - | GET | `/uapi/overseas-futureoption/v1/quotations/opt-tick-ccnl` | N | Y |
| 34 | 해외옵션 일별체결 | - | GET | `/uapi/overseas-futureoption/v1/quotations/opt-daily-ccnl` | Y | Y |
| 35 | 해외옵션 주별체결 | - | GET | `/uapi/overseas-futureoption/v1/quotations/opt-weekly-ccnl` | Y | Y |
| 36 | 해외옵션 월별체결 | - | GET | `/uapi/overseas-futureoption/v1/quotations/opt-monthly-ccnl` | Y | Y |

---

## 12. 국내채권 (Domestic Bond)

| # | API명 | tr_id | Method | URL Path | 과거조회 | 페이징 |
|---|-------|-------|--------|----------|---------|--------|
| 1 | 채권현재가 | FHKBJ773400C0 | GET | `/uapi/domestic-bond/v1/quotations/inquire-price` | N | Y |
| 2 | 채권호가 | - | GET | `/uapi/domestic-bond/v1/quotations/inquire-asking-price` | N | N |
| 3 | 채권체결 | - | GET | `/uapi/domestic-bond/v1/quotations/inquire-ccnl` | N | Y |
| 4 | 채권일자별시세 | - | GET | `/uapi/domestic-bond/v1/quotations/inquire-daily-price` | Y | Y |
| 5 | 채권기간별차트 | - | GET | `/uapi/domestic-bond/v1/quotations/inquire-daily-itemchartprice` | Y | Y |
| 6 | 채권지수체결 | - | GET | `/uapi/domestic-bond/v1/quotations/bond-index-ccnl` | N | Y |
| 7 | 채권종목검색 | - | GET | `/uapi/domestic-bond/v1/quotations/search-bond-info` | N | Y |
| 8 | 채권발행정보 | - | GET | `/uapi/domestic-bond/v1/quotations/issue-info` | N | N |
| 9 | 채권평균단가 | - | GET | `/uapi/domestic-bond/v1/quotations/avg-unit` | N | N |
| 10 | 채권매수주문 | TTTC0952U | POST | `/uapi/domestic-bond/v1/trading/buy` | CANO, PDNO, ORD_QTY, BOND_ORD_UNPR | N | N |
| 11 | 채권매도주문 | - | POST | `/uapi/domestic-bond/v1/trading/sell` | CANO, PDNO, ORD_QTY | N | N |
| 12 | 채권정정취소 | - | POST | `/uapi/domestic-bond/v1/trading/order-rvsecncl` | CANO, ORGN_ODNO | N | N |
| 13 | 채권잔고조회 | - | GET | `/uapi/domestic-bond/v1/trading/inquire-balance` | CANO | N | Y |
| 14 | 채권체결내역 | - | GET | `/uapi/domestic-bond/v1/trading/inquire-daily-ccld` | CANO, 기간 | Y | Y |
| 15 | 채권주문가능 | - | GET | `/uapi/domestic-bond/v1/trading/inquire-psbl-order` | CANO | N | N |
| 16 | 채권정정취소가능 | - | GET | `/uapi/domestic-bond/v1/trading/inquire-psbl-rvsecncl` | CANO | N | Y |

---

## 요약 통계

| 카테고리 | REST API 수 | WebSocket API 수 | 합계 |
|---------|-----------|-----------------|------|
| 인증 (OAuth) | 4 | 0 | 4 |
| 국내주식 시세 | ~95 | 3 | ~98 |
| 국내주식 주문/계좌 | 25 | 0 | 25 |
| 국내주식 재무 | 7 | 0 | 7 |
| 국내주식 순위분석 | 17 | 0 | 17 |
| 국내주식 종목정보(KSD) | 12 | 0 | 12 |
| 해외주식 시세 | 31 | 3 | 34 |
| 해외주식 주문/계좌 | 28 | 0 | 28 |
| ETF/ETN | 5 | 1 | 6 |
| ELW | 25 | 0 | 25 |
| 국내 선물옵션 | 29 | 15 | 44 |
| 해외 선물옵션 | 36 | 0 | 36 |
| 국내채권 | 16 | 0 | 16 |
| **합계** | **~330** | **~22** | **~352** |

---

## 기본 도메인

| 환경 | 도메인 |
|------|--------|
| 실전 | `https://openapi.koreainvestment.com:9443` |
| 모의 | `https://openapivts.koreainvestment.com:29443` |
| WebSocket(실전) | `ws://ops.koreainvestment.com:21000` |
| WebSocket(모의) | `ws://ops.koreainvestment.com:31000` |

## 공통 헤더

```
Content-Type: application/json; charset=utf-8
Authorization: Bearer {access_token}
appkey: {앱키}
appsecret: {앱시크릿}
tr_id: {거래ID}
tr_cont: {연속조회키 - 페이징시 "N"/"M"}
```

## 주요 거래소 코드 (해외)

| 코드 | 거래소 |
|------|--------|
| NAS | NASDAQ |
| NYS | NYSE |
| AMS | AMEX |
| HKS | 홍콩 |
| SHS | 상해 |
| SZS | 심천 |
| TSE | 도쿄 |
| HNX | 하노이 |
| HSX | 호치민 |

---

Sources:
- KIS Developers Portal: https://apiportal.koreainvestment.com/apiservice
- GitHub open-trading-api: https://github.com/koreainvestment/open-trading-api
- WikiDocs 트레이딩 예제: https://wikidocs.net/book/7559

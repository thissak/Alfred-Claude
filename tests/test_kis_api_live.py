#!/usr/bin/env python3
"""KIS API 실제 호출 테스트 — 응답 필드 구조 검증.

각 API를 실제로 호출하고, 스크리너에 필요한 필드가 존재하는지 확인한다.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from kis_readonly_client import get as kis_get

RESULTS = {}


def dump(label, data):
    """응답을 출력하고 결과에 저장."""
    print(f"\n{'='*80}")
    print(f"[{label}]")
    print(f"{'='*80}")
    if data is None:
        print("  → API 호출 실패 (None)")
        RESULTS[label] = None
        return None

    # output 또는 output1 추출
    output = data.get("output") or data.get("output1")
    if isinstance(output, list):
        print(f"  → {len(output)}건 반환")
        if output:
            print(f"  → 첫 번째 항목 키: {list(output[0].keys())}")
            print(json.dumps(output[0], indent=2, ensure_ascii=False))
    elif isinstance(output, dict):
        print(f"  → 키: {list(output.keys())}")
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        print(f"  → raw: {json.dumps(data, indent=2, ensure_ascii=False)[:2000]}")

    RESULTS[label] = data
    return data


# =====================================================================
# 1. 국내: 시가총액순위 (FHPST01740000) — 종목 풀 확보용
# =====================================================================
def test_kr_market_cap_ranking():
    data = kis_get(
        "/uapi/domestic-stock/v1/ranking/market-cap",
        "FHPST01740000",
        {
            "FID_COND_MRKT_DIV_CODE": "J",  # J=코스피
            "FID_COND_SCR_DIV_CODE": "20174",
            "FID_INPUT_ISCD": "0000",
            "FID_DIV_CLS_CODE": "0",
            "FID_TRGT_CLS_CODE": "0",
            "FID_TRGT_EXLS_CLS_CODE": "0",
            "FID_INPUT_PRICE_1": "",
            "FID_INPUT_PRICE_2": "",
            "FID_VOL_CNT": "",
            "FID_INPUT_DATE_1": "",
        },
    )
    dump("국내 시가총액순위", data)


# =====================================================================
# 2. 국내: 현재가 시세 (FHKST01010100) — 전체 응답 필드 덤프
# =====================================================================
def test_kr_inquire_price_full():
    data = kis_get(
        "/uapi/domestic-stock/v1/quotations/inquire-price",
        "FHKST01010100",
        {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": "005930"},
    )
    dump("국내 현재가(삼성전자) 전체필드", data)


# =====================================================================
# 3. 국내: 투자자별 매매동향 (FHKST01010900) — 종목별 수급
# =====================================================================
def test_kr_investor():
    data = kis_get(
        "/uapi/domestic-stock/v1/quotations/inquire-investor",
        "FHKST01010900",
        {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": "005930",
        },
    )
    dump("국내 투자자매매동향(삼성전자)", data)


# =====================================================================
# 4. 국내: 기간별시세 (FHKST03010100) — 일봉 데이터
# =====================================================================
def test_kr_daily_chart():
    data = kis_get(
        "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice",
        "FHKST03010100",
        {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": "005930",
            "FID_INPUT_DATE_1": "20260301",
            "FID_INPUT_DATE_2": "20260327",
            "FID_PERIOD_DIV_CODE": "D",
            "FID_ORG_ADJ_PRC": "0",
        },
    )
    dump("국내 일봉(삼성전자 3월)", data)


# =====================================================================
# 5. 해외: 조건검색 (HHDFS76410000) — US 스크리너 핵심
# =====================================================================
def test_us_search():
    data = kis_get(
        "/uapi/overseas-price/v1/quotations/inquire-search",
        "HHDFS76410000",
        {
            "AUTH": "",
            "EXCD": "NAS",
            "CO_YN_PRICECUR": "N", "CO_ST_PRICECUR": "", "CO_EN_PRICECUR": "",
            "CO_YN_RATE": "N", "CO_ST_RATE": "", "CO_EN_RATE": "",
            "CO_YN_VALX": "Y", "CO_ST_VALX": "100000000000", "CO_EN_VALX": "9999999999999",  # 시총 $1000억+
            "CO_YN_SHAR": "N", "CO_ST_SHAR": "", "CO_EN_SHAR": "",
            "CO_YN_VOLUME": "N", "CO_ST_VOLUME": "", "CO_EN_VOLUME": "",
            "CO_YN_AMT": "N", "CO_ST_AMT": "", "CO_EN_AMT": "",
            "CO_YN_EPS": "N", "CO_ST_EPS": "", "CO_EN_EPS": "",
            "CO_YN_PER": "N", "CO_ST_PER": "", "CO_EN_PER": "",
        },
    )
    dump("해외 조건검색(NAS 시총 $1000억+)", data)


# =====================================================================
# 6. 해외: 현재가 상세 (HHDFS76200200) — 펀더멘탈 포함
# =====================================================================
def test_us_price_detail():
    data = kis_get(
        "/uapi/overseas-price/v1/quotations/price-detail",
        "HHDFS76200200",
        {"AUTH": "", "EXCD": "NAS", "SYMB": "AAPL"},
    )
    dump("해외 현재가상세(AAPL)", data)


# =====================================================================
# 메인
# =====================================================================
if __name__ == "__main__":
    tests = [
        test_kr_market_cap_ranking,
        test_kr_inquire_price_full,
        test_kr_investor,
        test_kr_daily_chart,
        test_us_search,
        test_us_price_detail,
    ]

    for test in tests:
        try:
            test()
        except Exception as e:
            print(f"\n[ERROR] {test.__name__}: {e}")

    # 결과 저장
    out_path = ROOT / "data" / "kis_api_fields.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(RESULTS, ensure_ascii=False, indent=2))
    print(f"\n\n전체 응답 저장: {out_path}")

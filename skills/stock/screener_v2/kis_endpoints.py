"""KIS API 스크리너 엔드포인트 — 실제 응답 구조 기반.

각 함수는 kis_readonly_client.get() 호출 + 응답 파싱을 담당.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))
from kis_readonly_client import get as kis_get

from normalize import (
    normalize_kr_from_ranking,
    normalize_kr_from_inquire_price,
    enrich_kr_with_inquire_price,
    normalize_us_from_search,
    enrich_us_with_detail,
)


# =====================================================================
# 국내: 시가총액순위 — 종목 풀 확보 (30건씩 페이징)
# =====================================================================

def fetch_kr_market_cap_page(market: str = "J", page: int = 0) -> list[dict]:
    """시가총액순위 1페이지(30건) 조회 → 통합 스키마 리스트.

    Args:
        market: J=코스피, Q=코스닥
        page: 페이지 번호 (0부터)

    API 응답 키: mksc_shrn_iscd, hts_kor_isnm, stck_prpr, prdy_ctrt,
                 acml_vol, stck_avls (시총 억원)
    PER/PBR 없음 → enrich_kr_with_inquire_price()로 보강 필요.
    """
    # 페이징: FID_INPUT_PRICE_1 활용 (연속조회 키)
    data = kis_get(
        "/uapi/domestic-stock/v1/ranking/market-cap",
        "FHPST01740000",
        {
            "FID_COND_MRKT_DIV_CODE": market,
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
    if not data or not data.get("output"):
        return []
    return [normalize_kr_from_ranking(item) for item in data["output"]]


# =====================================================================
# 국내: 현재가 시세 — 종목별 상세 (PER/PBR/외인 등)
# =====================================================================

def fetch_kr_price_detail(code: str) -> dict | None:
    """개별 종목 현재가 조회 → raw output dict.

    API 응답 키: per, pbr, eps, bps, hts_frgn_ehrt, frgn_ntby_qty,
                 w52_hgpr, w52_lwpr, bstp_kor_isnm, hts_avls, ...
    """
    data = kis_get(
        "/uapi/domestic-stock/v1/quotations/inquire-price",
        "FHKST01010100",
        {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code},
    )
    if not data:
        return None
    return data.get("output")


# =====================================================================
# 국내: 투자자 매매동향 — 30일 외인/기관/개인 수급
# =====================================================================

def fetch_kr_investor(code: str) -> list[dict]:
    """종목별 투자자 매매동향 30일.

    API 응답 키 (일별): stck_bsop_date, frgn_ntby_qty, orgn_ntby_qty,
                        prsn_ntby_qty, frgn_ntby_tr_pbmn, ...
    """
    data = kis_get(
        "/uapi/domestic-stock/v1/quotations/inquire-investor",
        "FHKST01010900",
        {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": code,
        },
    )
    if not data:
        return []
    return data.get("output", [])


def sum_investor_days(investor_data: list[dict], days: int = 5) -> dict:
    """투자자 매매동향 N일 합계.

    Returns: {"foreign_net": 총합, "institution_net": 총합, "individual_net": 총합}
    """
    foreign = 0
    institution = 0
    individual = 0
    for item in investor_data[:days]:
        f = item.get("frgn_ntby_qty", "")
        o = item.get("orgn_ntby_qty", "")
        p = item.get("prsn_ntby_qty", "")
        if f:
            foreign += int(f)
        if o:
            institution += int(o)
        if p:
            individual += int(p)
    return {
        "foreign_net": foreign,
        "institution_net": institution,
        "individual_net": individual,
    }


# =====================================================================
# 해외: 조건검색 — US 스크리너 핵심
# =====================================================================

def fetch_us_search(
    exchange: str = "NAS",
    per_range: tuple[float, float] | None = None,
    mktcap_range: tuple[int, int] | None = None,
    eps_range: tuple[float, float] | None = None,
    volume_range: tuple[int, int] | None = None,
    price_range: tuple[float, float] | None = None,
) -> list[dict]:
    """해외주식 조건검색 → 통합 스키마 리스트 (최대 100건).

    주의: valx (시가총액) 파라미터는 9자리 제한.

    API 응답 키: symb, name, last, rate, tvol, valx, eps, per, avol, popen, phigh, plow
    """
    def _yn(rng):
        return "Y" if rng else "N"

    def _val(rng, idx):
        return str(int(rng[idx])) if rng else ""

    data = kis_get(
        "/uapi/overseas-price/v1/quotations/inquire-search",
        "HHDFS76410000",
        {
            "AUTH": "",
            "EXCD": exchange,
            "CO_YN_PRICECUR": _yn(price_range),
            "CO_ST_PRICECUR": _val(price_range, 0) if price_range else "",
            "CO_EN_PRICECUR": _val(price_range, 1) if price_range else "",
            "CO_YN_RATE": "N", "CO_ST_RATE": "", "CO_EN_RATE": "",
            "CO_YN_VALX": _yn(mktcap_range),
            "CO_ST_VALX": _val(mktcap_range, 0) if mktcap_range else "",
            "CO_EN_VALX": _val(mktcap_range, 1) if mktcap_range else "",
            "CO_YN_SHAR": "N", "CO_ST_SHAR": "", "CO_EN_SHAR": "",
            "CO_YN_VOLUME": _yn(volume_range),
            "CO_ST_VOLUME": _val(volume_range, 0) if volume_range else "",
            "CO_EN_VOLUME": _val(volume_range, 1) if volume_range else "",
            "CO_YN_AMT": "N", "CO_ST_AMT": "", "CO_EN_AMT": "",
            "CO_YN_EPS": _yn(eps_range),
            "CO_ST_EPS": _val(eps_range, 0) if eps_range else "",
            "CO_EN_EPS": _val(eps_range, 1) if eps_range else "",
            "CO_YN_PER": _yn(per_range),
            "CO_ST_PER": _val(per_range, 0) if per_range else "",
            "CO_EN_PER": _val(per_range, 1) if per_range else "",
        },
    )
    if not data:
        return []
    output = data.get("output2") or data.get("output1") or data.get("output") or []
    return [normalize_us_from_search(item) for item in output]


# =====================================================================
# 해외: 현재가상세 — PBR, 52주, 업종 등 보강
# =====================================================================

def fetch_us_price_detail(code: str, exchange: str = "NAS") -> dict | None:
    """해외 종목 상세 조회 → raw output dict.

    API 응답 키: perx, pbrx, epsx, bpsx, h52p, l52p, e_icod, mcap, tomv, ...
    """
    data = kis_get(
        "/uapi/overseas-price/v1/quotations/price-detail",
        "HHDFS76200200",
        {"AUTH": "", "EXCD": exchange, "SYMB": code},
    )
    if not data:
        return None
    return data.get("output")

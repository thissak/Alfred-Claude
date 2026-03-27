"""KIS API 실제 응답 → 통합 스키마 정규화.

국내: inquire-price output + market-cap ranking output
해외: inquire-search output + price-detail output
"""

from __future__ import annotations

# API에서 직접 가져오는 필드만 포함 (자체 계산 없음)
UNIFIED_SCHEMA_KEYS = [
    # 식별
    "code", "name", "market", "sector",
    # 가격
    "price", "change_rate", "volume",
    "open", "high", "low",
    "w52_high", "w52_low",
    # 밸류에이션
    "mktcap", "per", "pbr", "eps", "bps",
    # 수급 (국내 전용, 해외는 None)
    "foreign_ratio", "foreign_net",
    # 재무 (마스터 파일 or 손익계산서)
    "roe", "oper_profit", "revenue",
    # 해외 전용
    "avg_volume",  # 평균거래량
]


def _safe_int(v, default=None):
    if v is None or v == "":
        return default
    try:
        return int(v)
    except (ValueError, TypeError):
        return default


def _safe_float(v, default=None):
    if v is None or v == "":
        return default
    try:
        return float(str(v).replace("+", ""))
    except (ValueError, TypeError):
        return default


def _make_empty() -> dict:
    return {k: None for k in UNIFIED_SCHEMA_KEYS}


def normalize_kr_from_inquire_price(code: str, name: str, output: dict) -> dict:
    """국내 inquire-price API output → 통합 스키마.

    API: /uapi/domestic-stock/v1/quotations/inquire-price (FHKST01010100)
    """
    s = _make_empty()
    s["code"] = code
    s["name"] = name
    s["market"] = "KR"
    s["price"] = _safe_int(output.get("stck_prpr"))
    s["change_rate"] = _safe_float(output.get("prdy_ctrt"))
    s["volume"] = _safe_int(output.get("acml_vol"))
    s["open"] = _safe_int(output.get("stck_oprc"))
    s["high"] = _safe_int(output.get("stck_hgpr"))
    s["low"] = _safe_int(output.get("stck_lwpr"))
    s["per"] = _safe_float(output.get("per"))
    s["pbr"] = _safe_float(output.get("pbr"))
    s["eps"] = _safe_float(output.get("eps"))
    s["bps"] = _safe_float(output.get("bps"))
    s["mktcap"] = _safe_int(output.get("hts_avls"))
    s["foreign_ratio"] = _safe_float(output.get("hts_frgn_ehrt"))
    s["foreign_net"] = _safe_int(output.get("frgn_ntby_qty"))
    s["w52_high"] = _safe_int(output.get("w52_hgpr"))
    s["w52_low"] = _safe_int(output.get("w52_lwpr"))
    s["sector"] = output.get("bstp_kor_isnm")
    return s


def normalize_kr_from_ranking(item: dict) -> dict:
    """국내 market-cap ranking output → 통합 스키마 (기본 정보만).

    API: /uapi/domestic-stock/v1/ranking/market-cap (FHPST01740000)
    PER/PBR 없음 — inquire-price로 보강 필요.
    """
    s = _make_empty()
    s["code"] = item.get("mksc_shrn_iscd", "")
    s["name"] = item.get("hts_kor_isnm", "")
    s["market"] = "KR"
    s["price"] = _safe_int(item.get("stck_prpr"))
    s["change_rate"] = _safe_float(item.get("prdy_ctrt"))
    s["volume"] = _safe_int(item.get("acml_vol"))
    s["mktcap"] = _safe_int(item.get("stck_avls"))
    return s


def enrich_kr_with_inquire_price(stock: dict, output: dict) -> dict:
    """market-cap ranking으로 만든 stock에 inquire-price 데이터 보강."""
    stock["per"] = _safe_float(output.get("per"))
    stock["pbr"] = _safe_float(output.get("pbr"))
    stock["eps"] = _safe_float(output.get("eps"))
    stock["bps"] = _safe_float(output.get("bps"))
    stock["foreign_ratio"] = _safe_float(output.get("hts_frgn_ehrt"))
    stock["foreign_net"] = _safe_int(output.get("frgn_ntby_qty"))
    stock["w52_high"] = _safe_int(output.get("w52_hgpr"))
    stock["w52_low"] = _safe_int(output.get("w52_lwpr"))
    stock["sector"] = output.get("bstp_kor_isnm")
    stock["open"] = _safe_int(output.get("stck_oprc"))
    stock["high"] = _safe_int(output.get("stck_hgpr"))
    stock["low"] = _safe_int(output.get("stck_lwpr"))
    # mktcap 갱신 (API가 더 최신)
    api_mktcap = _safe_int(output.get("hts_avls"))
    if api_mktcap:
        stock["mktcap"] = api_mktcap
    return stock


def normalize_us_from_search(item: dict) -> dict:
    """해외 inquire-search output → 통합 스키마.

    API: /uapi/overseas-price/v1/quotations/inquire-search (HHDFS76410000)
    """
    s = _make_empty()
    s["code"] = item.get("symb", "")
    s["name"] = item.get("name", "")
    s["market"] = "US"
    s["price"] = _safe_float(item.get("last"))
    s["change_rate"] = _safe_float(item.get("rate"))
    s["volume"] = _safe_int(item.get("tvol"))
    s["open"] = _safe_float(item.get("popen"))
    s["high"] = _safe_float(item.get("phigh"))
    s["low"] = _safe_float(item.get("plow"))
    s["mktcap"] = _safe_int(item.get("valx"))
    s["eps"] = _safe_float(item.get("eps"))
    s["per"] = _safe_float(item.get("per"))
    s["avg_volume"] = _safe_int(item.get("avol"))
    s["sector"] = item.get("excd")  # 거래소 (NAS/NYS/AMS)
    return s


def enrich_us_with_detail(stock: dict, output: dict) -> dict:
    """inquire-search로 만든 stock에 price-detail 데이터 보강.

    API: /uapi/overseas-price/v1/quotations/price-detail (HHDFS76200200)
    """
    stock["pbr"] = _safe_float(output.get("pbrx"))
    stock["bps"] = _safe_float(output.get("bpsx"))
    stock["w52_high"] = _safe_float(output.get("h52p"))
    stock["w52_low"] = _safe_float(output.get("l52p"))
    # price-detail의 PER/EPS가 더 정확할 수 있음
    perx = _safe_float(output.get("perx"))
    if perx is not None:
        stock["per"] = perx
    epsx = _safe_float(output.get("epsx"))
    if epsx is not None:
        stock["eps"] = epsx
    # 업종 (e_icod가 더 상세)
    e_icod = output.get("e_icod")
    if e_icod:
        stock["sector"] = e_icod
    return stock

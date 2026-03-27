"""정규화 단위 테스트 — 실제 KIS API 응답 구조 기반."""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills" / "stock" / "screener_v2"))
from normalize import (
    normalize_kr_from_inquire_price,
    normalize_kr_from_ranking,
    enrich_kr_with_inquire_price,
    normalize_us_from_search,
    enrich_us_with_detail,
    UNIFIED_SCHEMA_KEYS,
)


# --- 실제 API 응답 샘플 (2026-03-27 삼성전자) ---

REAL_KR_INQUIRE_PRICE = {
    "stck_prpr": "180100",
    "prdy_vrss": "0",
    "prdy_ctrt": "0.00",
    "acml_vol": "395",
    "stck_oprc": "0",
    "stck_hgpr": "0",
    "stck_lwpr": "0",
    "hts_avls": "10661268",
    "per": "27.44",
    "pbr": "2.81",
    "eps": "6564.00",
    "bps": "63997.00",
    "hts_frgn_ehrt": "48.90",
    "frgn_ntby_qty": "0",
    "w52_hgpr": "223000",
    "w52_lwpr": "52900",
    "bstp_kor_isnm": "전기·전자",
    "d250_hgpr": "223000",
}

REAL_KR_RANKING_ITEM = {
    "mksc_shrn_iscd": "005930",
    "data_rank": "1",
    "hts_kor_isnm": "삼성전자",
    "stck_prpr": "180100",
    "prdy_vrss": "0",
    "prdy_ctrt": "0.00",
    "acml_vol": "395",
    "lstn_stcn": "5919637922",
    "stck_avls": "10661268",
}

REAL_US_SEARCH_ITEM = {
    "rsym": "DNASNVDA",
    "excd": "NAS",
    "symb": "NVDA",
    "name": "엔비디아",
    "last": "172.2700",
    "sign": "5",
    "diff": "6.4100",
    "rate": "-3.59",
    "tvol": "132097141",
    "popen": "176.0700",
    "phigh": "176.5100",
    "plow": "171.0900",
    "valx": "4186161000",
    "shar": "24300000000",
    "avol": "22891095475",
    "eps": "4.90",
    "per": "35.15",
    "rank": "2",
    "ename": "NVIDIA CORP",
    "e_ordyn": "○",
}

REAL_US_DETAIL = {
    "rsym": "DNASAAPL",
    "perx": "32.21",
    "pbrx": "42.44",
    "epsx": "7.90",
    "bpsx": "6.00",
    "h52p": "288.3501",
    "l52p": "168.4757",
    "mcap": "95221000000",
    "e_icod": "컴퓨터전자장비/기기",
    "last": "254.5500",
    "tvol": "30895461",
}


# --- 국내 inquire-price 정규화 ---

class TestNormalizeKRFromPrice:
    def test_basic_fields(self):
        r = normalize_kr_from_inquire_price("005930", "삼성전자", REAL_KR_INQUIRE_PRICE)
        assert r["code"] == "005930"
        assert r["name"] == "삼성전자"
        assert r["market"] == "KR"
        assert r["price"] == 180100

    def test_valuation(self):
        r = normalize_kr_from_inquire_price("005930", "삼성전자", REAL_KR_INQUIRE_PRICE)
        assert r["per"] == 27.44
        assert r["pbr"] == 2.81
        assert r["eps"] == 6564.0
        assert r["bps"] == 63997.0

    def test_mktcap(self):
        r = normalize_kr_from_inquire_price("005930", "삼성전자", REAL_KR_INQUIRE_PRICE)
        assert r["mktcap"] == 10661268  # 억원

    def test_foreign(self):
        r = normalize_kr_from_inquire_price("005930", "삼성전자", REAL_KR_INQUIRE_PRICE)
        assert r["foreign_ratio"] == 48.90
        assert r["foreign_net"] == 0

    def test_52week(self):
        r = normalize_kr_from_inquire_price("005930", "삼성전자", REAL_KR_INQUIRE_PRICE)
        assert r["w52_high"] == 223000
        assert r["w52_low"] == 52900

    def test_sector(self):
        r = normalize_kr_from_inquire_price("005930", "삼성전자", REAL_KR_INQUIRE_PRICE)
        assert r["sector"] == "전기·전자"

    def test_all_keys_present(self):
        r = normalize_kr_from_inquire_price("005930", "삼성전자", REAL_KR_INQUIRE_PRICE)
        for key in UNIFIED_SCHEMA_KEYS:
            assert key in r, f"missing key: {key}"


# --- 국내 ranking 정규화 ---

class TestNormalizeKRFromRanking:
    def test_basic(self):
        r = normalize_kr_from_ranking(REAL_KR_RANKING_ITEM)
        assert r["code"] == "005930"
        assert r["name"] == "삼성전자"
        assert r["mktcap"] == 10661268
        assert r["price"] == 180100

    def test_no_per_pbr(self):
        """시가총액순위 API에는 PER/PBR 없음."""
        r = normalize_kr_from_ranking(REAL_KR_RANKING_ITEM)
        assert r["per"] is None
        assert r["pbr"] is None

    def test_all_keys_present(self):
        r = normalize_kr_from_ranking(REAL_KR_RANKING_ITEM)
        for key in UNIFIED_SCHEMA_KEYS:
            assert key in r, f"missing key: {key}"


# --- 국내 enrich ---

class TestEnrichKR:
    def test_enrich_adds_per(self):
        stock = normalize_kr_from_ranking(REAL_KR_RANKING_ITEM)
        assert stock["per"] is None
        enrich_kr_with_inquire_price(stock, REAL_KR_INQUIRE_PRICE)
        assert stock["per"] == 27.44
        assert stock["pbr"] == 2.81
        assert stock["sector"] == "전기·전자"


# --- 해외 inquire-search 정규화 ---

class TestNormalizeUSFromSearch:
    def test_basic(self):
        r = normalize_us_from_search(REAL_US_SEARCH_ITEM)
        assert r["code"] == "NVDA"
        assert r["name"] == "엔비디아"
        assert r["market"] == "US"

    def test_price(self):
        r = normalize_us_from_search(REAL_US_SEARCH_ITEM)
        assert r["price"] == pytest.approx(172.27)
        assert r["change_rate"] == pytest.approx(-3.59)

    def test_valuation(self):
        r = normalize_us_from_search(REAL_US_SEARCH_ITEM)
        assert r["per"] == pytest.approx(35.15)
        assert r["eps"] == pytest.approx(4.90)
        assert r["mktcap"] == 4186161000

    def test_volume(self):
        r = normalize_us_from_search(REAL_US_SEARCH_ITEM)
        assert r["volume"] == 132097141
        assert r["avg_volume"] == 22891095475

    def test_ohlc(self):
        r = normalize_us_from_search(REAL_US_SEARCH_ITEM)
        assert r["open"] == pytest.approx(176.07)
        assert r["high"] == pytest.approx(176.51)
        assert r["low"] == pytest.approx(171.09)

    def test_kr_fields_none(self):
        r = normalize_us_from_search(REAL_US_SEARCH_ITEM)
        assert r["foreign_ratio"] is None
        assert r["foreign_net"] is None

    def test_all_keys_present(self):
        r = normalize_us_from_search(REAL_US_SEARCH_ITEM)
        for key in UNIFIED_SCHEMA_KEYS:
            assert key in r, f"missing key: {key}"


# --- 해외 enrich ---

class TestEnrichUS:
    def test_enrich_adds_pbr(self):
        stock = normalize_us_from_search(REAL_US_SEARCH_ITEM)
        assert stock["pbr"] is None
        enrich_us_with_detail(stock, REAL_US_DETAIL)
        assert stock["pbr"] == 42.44
        assert stock["w52_high"] == pytest.approx(288.3501)
        assert stock["sector"] == "컴퓨터전자장비/기기"

    def test_enrich_overrides_per(self):
        """price-detail의 PER이 더 정확."""
        stock = normalize_us_from_search(REAL_US_SEARCH_ITEM)
        assert stock["per"] == pytest.approx(35.15)
        enrich_us_with_detail(stock, REAL_US_DETAIL)
        assert stock["per"] == pytest.approx(32.21)


# --- KR/US 키 일치 ---

class TestUnifiedSchema:
    def test_kr_us_same_keys(self):
        kr = normalize_kr_from_inquire_price("005930", "삼성전자", REAL_KR_INQUIRE_PRICE)
        us = normalize_us_from_search(REAL_US_SEARCH_ITEM)
        assert set(kr.keys()) == set(us.keys())

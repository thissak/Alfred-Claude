"""필터 엔진 단위 테스트 — 실제 API 데이터 구조 기반."""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills" / "stock" / "screener_v2"))
from filters import Filter, apply_filters, PRESETS


# --- 실제 API 응답 기반 테스트 종목 ---

SAMPLE_STOCKS = [
    {   # 삼성전자 (실제 inquire-price 기반)
        "code": "005930", "name": "삼성전자", "market": "KR",
        "price": 180100, "mktcap": 10661268,
        "per": 27.44, "pbr": 2.81, "eps": 6564.0, "bps": 63997.0,
        "change_rate": 0.0, "volume": 395,
        "foreign_ratio": 48.90, "foreign_net": 0,
        "roe": None, "oper_profit": None, "revenue": None,
        "w52_high": 223000, "w52_low": 52900,
        "sector": "전기·전자",
        "open": None, "high": None, "low": None, "avg_volume": None,
    },
    {   # NVDA (실제 inquire-search 기반)
        "code": "NVDA", "name": "엔비디아", "market": "US",
        "price": 172.27, "mktcap": 4186161000,
        "per": 35.15, "pbr": None, "eps": 4.90, "bps": None,
        "change_rate": -3.59, "volume": 132097141,
        "foreign_ratio": None, "foreign_net": None,
        "roe": None, "oper_profit": None, "revenue": None,
        "w52_high": None, "w52_low": None,
        "sector": "NAS",
        "open": 176.07, "high": 176.51, "low": 171.09, "avg_volume": 22891095475,
    },
    {   # 가상 저PER 종목
        "code": "000660", "name": "SK하이닉스", "market": "KR",
        "price": 130000, "mktcap": 950000,
        "per": 5.8, "pbr": 1.8, "eps": 22414.0, "bps": 72222.0,
        "change_rate": 3.2, "volume": 8000000,
        "foreign_ratio": 52.1, "foreign_net": 300000,
        "roe": None, "oper_profit": None, "revenue": None,
        "w52_high": 150000, "w52_low": 80000,
        "sector": "전기·전자",
        "open": 128000, "high": 131000, "low": 127500, "avg_volume": None,
    },
]


# --- Filter 연산자 ---

class TestFilter:
    def test_gte(self):
        f = Filter("per", ">=", 10)
        assert f.match(SAMPLE_STOCKS[0])  # 27.44
        assert not f.match(SAMPLE_STOCKS[2])  # 5.8

    def test_lte(self):
        assert Filter("per", "<=", 10).match(SAMPLE_STOCKS[2])

    def test_gt(self):
        assert Filter("change_rate", ">", 0).match(SAMPLE_STOCKS[2])  # 3.2
        assert not Filter("change_rate", ">", 0).match(SAMPLE_STOCKS[1])  # -3.59

    def test_lt(self):
        assert Filter("change_rate", "<", 0).match(SAMPLE_STOCKS[1])

    def test_eq(self):
        assert Filter("market", "==", "KR").match(SAMPLE_STOCKS[0])
        assert not Filter("market", "==", "KR").match(SAMPLE_STOCKS[1])

    def test_ne(self):
        assert Filter("market", "!=", "US").match(SAMPLE_STOCKS[0])

    def test_between(self):
        f = Filter("per", "between", (5, 30))
        assert f.match(SAMPLE_STOCKS[0])  # 27.44
        assert f.match(SAMPLE_STOCKS[2])  # 5.8
        assert not f.match(SAMPLE_STOCKS[1])  # 35.15

    def test_none_value_skipped(self):
        """None 필드는 필터 불통과."""
        assert not Filter("foreign_ratio", ">", 50).match(SAMPLE_STOCKS[1])

    def test_repr(self):
        assert "per" in repr(Filter("per", "<=", 10))


# --- apply_filters ---

class TestApplyFilters:
    def test_single_filter(self):
        result = apply_filters(SAMPLE_STOCKS, [Filter("per", "between", (0, 30))])
        names = [s["name"] for s in result]
        assert "삼성전자" in names
        assert "SK하이닉스" in names
        assert "엔비디아" not in names  # 35.15

    def test_multiple_and(self):
        filters = [
            Filter("per", "between", (0, 30)),
            Filter("foreign_ratio", ">", 50),
        ]
        result = apply_filters(SAMPLE_STOCKS, filters)
        assert len(result) == 1
        assert result[0]["name"] == "SK하이닉스"

    def test_empty_filters_returns_all(self):
        assert len(apply_filters(SAMPLE_STOCKS, [])) == 3

    def test_market_filter(self):
        result = apply_filters(SAMPLE_STOCKS, [Filter("market", "==", "US")])
        assert len(result) == 1
        assert result[0]["code"] == "NVDA"

    def test_sort_by(self):
        result = apply_filters(SAMPLE_STOCKS, [Filter("per", ">", 0)], sort_by="per")
        assert result[0]["name"] == "SK하이닉스"  # 5.8
        assert result[-1]["name"] == "엔비디아"  # 35.15

    def test_sort_desc(self):
        result = apply_filters(SAMPLE_STOCKS, [], sort_by="price", ascending=False)
        assert result[0]["name"] == "삼성전자"  # 180100

    def test_limit(self):
        assert len(apply_filters(SAMPLE_STOCKS, [], limit=1)) == 1


# --- 프리셋 ---

class TestPresets:
    def test_value_preset(self):
        result = apply_filters(SAMPLE_STOCKS, PRESETS["저평가"])
        names = [s["name"] for s in result]
        assert "SK하이닉스" in names  # PER 5.8, PBR 1.8
        assert "삼성전자" not in names  # PBR 2.81

    def test_momentum_preset(self):
        assert "모멘텀" in PRESETS

    def test_supply_preset(self):
        result = apply_filters(SAMPLE_STOCKS, PRESETS["수급"])
        names = [s["name"] for s in result]
        assert "SK하이닉스" in names  # foreign_net 300000, volume 8M

    def test_all_presets_exist(self):
        for name in ["저평가", "모멘텀", "수급", "성장"]:
            assert name in PRESETS

"""종목 종합 분석 스크립트 — market.db + 네이버 증권 API."""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Union
from urllib.request import urlopen, Request
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_USE_MARKET_DB = bool(os.environ.get("MARKET_DB_HOST"))

if _USE_MARKET_DB:
    from src.market_db import _query
else:
    from src.kis_readonly_client import get as kis_get


# ── 네이버 증권 API ───────────────────────────────────────

NAVER_API = "https://m.stock.naver.com/api"


def _naver_get(path: str, params: Optional[dict] = None) -> Optional[Union[dict, list]]:
    url = f"{NAVER_API}{path}"
    if params:
        url += "?" + urlencode(params)
    req = Request(url, headers={
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://m.stock.naver.com/",
    })
    try:
        with urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"[WARN] Naver API error: {e}", file=sys.stderr)
        return None


def fetch_naver_news(code: str, page_size: int = 20) -> list[dict]:
    """네이버 증권 종목 뉴스."""
    data = _naver_get(f"/news/stock/{code}", {"pageSize": page_size, "page": 1})
    if not data:
        return []
    articles = []
    for cluster in data:
        for item in cluster.get("items", []):
            articles.append({
                "title": item.get("titleFull") or item.get("title", ""),
                "datetime": item.get("datetime", ""),
                "office": item.get("officeName", ""),
                "url": item.get("mobileNewsUrl", ""),
                "body": item.get("body", ""),
            })
    return articles


def fetch_naver_disclosure(code: str, page_size: int = 10) -> list[dict]:
    """네이버 증권 공시."""
    data = _naver_get(f"/stock/{code}/disclosure", {"page": 1, "pageSize": page_size})
    if not data:
        return []
    return [
        {
            "title": d.get("title", ""),
            "datetime": d.get("datetime", ""),
        }
        for d in data
    ]


def fetch_naver_integration(code: str) -> Optional[dict]:
    """네이버 증권 종목 기본 정보 (시세/지표)."""
    return _naver_get(f"/stock/{code}/integration")


# ── Market DB / KIS API ───────────────────────────────────

def fetch_basic_info(code: str) -> Optional[dict]:
    """종목 기본 정보 (securities 테이블)."""
    if _USE_MARKET_DB:
        rows = _query(
            "SELECT code, name, market, sector, mktcap FROM securities WHERE code=?",
            [code],
        )
        return rows[0] if rows else None
    # KIS API fallback — 현재가 조회로 기본 정보
    res = kis_get(
        "/uapi/domestic-stock/v1/quotations/inquire-price",
        "FHKST01010100",
        {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code},
    )
    if not res or res.get("rt_cd") != "0":
        return None
    out = res.get("output", {})
    return {
        "code": code,
        "name": out.get("hts_kor_isnm", ""),
        "market": "KOSPI" if out.get("rprs_mrkt_kor_name", "").startswith("코스피") else "KOSDAQ",
        "sector": "",
        "mktcap": int(out.get("hts_avls", "0")) if out.get("hts_avls") else 0,
    }


def fetch_daily_prices(code: str, days: int = 60) -> list[dict]:
    """일봉 데이터."""
    if _USE_MARKET_DB:
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        end = datetime.now().strftime("%Y-%m-%d")
        rows = _query(
            "SELECT date, open, high, low, close, volume, change_rate "
            "FROM daily_prices WHERE code=? AND date>=? AND date<=? ORDER BY date",
            [code, start, end],
        )
        return [dict(r) for r in rows]
    # KIS API
    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
    res = kis_get(
        "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice",
        "FHKST03010100",
        {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": code,
            "FID_INPUT_DATE_1": start,
            "FID_INPUT_DATE_2": end,
            "FID_PERIOD_DIV_CODE": "D",
            "FID_ORG_ADJ_PRC": "0",
        },
    )
    if not res:
        return []
    items = res.get("output2", [])
    parsed = []
    for item in items:
        try:
            parsed.append({
                "date": item["stck_bsop_date"],
                "open": int(item["stck_oprc"]),
                "high": int(item["stck_hgpr"]),
                "low": int(item["stck_lwpr"]),
                "close": int(item["stck_clpr"]),
                "volume": int(item["acml_vol"]),
                "change_rate": float(item.get("prdy_ctrt", 0)),
            })
        except (KeyError, ValueError):
            continue
    return sorted(parsed, key=lambda x: x["date"])


def fetch_valuation(code: str) -> Optional[dict]:
    """최신 밸류에이션 (PER/PBR/EPS/BPS/외인비율)."""
    if _USE_MARKET_DB:
        rows = _query(
            "SELECT * FROM daily_valuations WHERE code=? ORDER BY date DESC LIMIT 1",
            [code],
        )
        return dict(rows[0]) if rows else None
    return None


def fetch_investor_flow(code: str, days: int = 20) -> list[dict]:
    """투자자별 수급 (외인/기관/개인)."""
    if _USE_MARKET_DB:
        rows = _query(
            "SELECT date, foreign_net, institution_net, individual_net "
            "FROM investor_flow WHERE code=? ORDER BY date DESC LIMIT ?",
            [code, days],
        )
        return [dict(r) for r in rows]
    # KIS API
    res = kis_get(
        "/uapi/domestic-stock/v1/quotations/inquire-investor",
        "FHKST01010900",
        {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code},
    )
    if not res:
        return []
    items = res.get("output", [])
    parsed = []
    for item in items[:days]:
        try:
            parsed.append({
                "date": item["stck_bsop_date"],
                "foreign_net": int(item["frgn_ntby_qty"]),
                "institution_net": int(item["orgn_ntby_qty"]),
                "individual_net": int(item["prsn_ntby_qty"]),
            })
        except (KeyError, ValueError):
            continue
    return parsed


def fetch_financials(code: str) -> list[dict]:
    """재무제표 (최근 연간/분기)."""
    if _USE_MARKET_DB:
        rows = _query(
            "SELECT * FROM financials WHERE code=? ORDER BY period DESC LIMIT 8",
            [code],
        )
        return [dict(r) for r in rows]
    return []


def fetch_screening(code: str) -> Optional[dict]:
    """스크리닝 지표 (MA, 수익률, 거래량비율 등)."""
    if _USE_MARKET_DB:
        rows = _query(
            "SELECT * FROM daily_screening WHERE code=? ORDER BY date DESC LIMIT 1",
            [code],
        )
        return dict(rows[0]) if rows else None
    return None


def fetch_short_selling(code: str, days: int = 20) -> list[dict]:
    """공매도 데이터."""
    if _USE_MARKET_DB:
        rows = _query(
            "SELECT date, short_volume, short_value, short_ratio "
            "FROM daily_short_selling WHERE code=? ORDER BY date DESC LIMIT ?",
            [code, days],
        )
        return [dict(r) for r in rows]
    return []


# ── 분석 함수 ─────────────────────────────────────────────

def calc_trend(prices: list[dict]) -> dict:
    """가격 추세 요약."""
    if len(prices) < 2:
        return {}
    latest = prices[-1]
    closes = [p["close"] for p in prices]
    volumes = [p["volume"] for p in prices]

    # 이평선
    def ma(n):
        return round(sum(closes[-n:]) / n) if len(closes) >= n else None

    # 거래량 평균
    avg_vol_20 = round(sum(volumes[-20:]) / min(len(volumes), 20))

    return {
        "latest_date": latest["date"],
        "latest_close": latest["close"],
        "latest_volume": latest["volume"],
        "ma5": ma(5),
        "ma20": ma(20),
        "ma60": ma(60),
        "vol_avg_20d": avg_vol_20,
        "vol_ratio": round(latest["volume"] / avg_vol_20, 2) if avg_vol_20 > 0 else 0,
        "return_5d": round((closes[-1] / closes[-6] - 1) * 100, 2) if len(closes) >= 6 else None,
        "return_20d": round((closes[-1] / closes[-21] - 1) * 100, 2) if len(closes) >= 21 else None,
        "high_60d": max(closes),
        "low_60d": min(closes),
        "from_high": round((closes[-1] / max(closes) - 1) * 100, 2),
        "from_low": round((closes[-1] / min(closes) - 1) * 100, 2),
    }


def summarize_investor(flows: list[dict]) -> dict:
    """수급 요약."""
    if not flows:
        return {}
    foreign_total = sum(f.get("foreign_net", 0) for f in flows)
    inst_total = sum(f.get("institution_net", 0) for f in flows)
    indiv_total = sum(f.get("individual_net", 0) for f in flows)
    return {
        "days": len(flows),
        "foreign_net_total": foreign_total,
        "institution_net_total": inst_total,
        "individual_net_total": indiv_total,
        "foreign_trend": "매수" if foreign_total > 0 else "매도",
        "institution_trend": "매수" if inst_total > 0 else "매도",
    }


# ── 메인 ──────────────────────────────────────────────────

def analyze(code: str, name: str = "") -> dict:
    """종합 분석 실행."""
    result = {"code": code, "name": name, "timestamp": datetime.now().isoformat()}

    # 1. 기본 정보
    info = fetch_basic_info(code)
    if info:
        result["name"] = result["name"] or info.get("name", "")
        result["info"] = info

    # 2. 일봉
    prices = fetch_daily_prices(code, days=90)
    result["trend"] = calc_trend(prices)
    result["prices_count"] = len(prices)

    # 3. 밸류에이션
    val = fetch_valuation(code)
    if val:
        result["valuation"] = val

    # 4. 수급
    flows = fetch_investor_flow(code, days=20)
    result["investor"] = summarize_investor(flows)
    result["investor_detail"] = flows[:5]  # 최근 5일 상세

    # 5. 재무
    fins = fetch_financials(code)
    if fins:
        result["financials"] = fins[:4]  # 최근 4기

    # 6. 스크리닝 지표
    scr = fetch_screening(code)
    if scr:
        result["screening"] = scr

    # 7. 공매도
    shorts = fetch_short_selling(code, days=5)
    if shorts:
        result["short_selling"] = shorts

    # 8. 네이버 뉴스
    news = fetch_naver_news(code, page_size=15)
    result["naver_news"] = news[:10]  # 상위 10건

    # 9. 네이버 공시
    disclosures = fetch_naver_disclosure(code, page_size=10)
    result["disclosures"] = disclosures

    # 10. 네이버 시세 (보조)
    naver_info = fetch_naver_integration(code)
    if naver_info:
        result["naver_integration"] = naver_info

    return result


def print_report(data: dict):
    """분석 결과를 터미널에 출력."""
    name = data.get("name", "")
    code = data.get("code", "")
    print(f"\n{'='*60}")
    print(f" {name} ({code}) 종합 분석")
    print(f"{'='*60}")

    # 기본 정보
    info = data.get("info", {})
    if info:
        print(f"\n[기본정보]")
        print(f"  시장: {info.get('market', '-')}  |  섹터: {info.get('sector', '-')}")
        mktcap = info.get("mktcap", 0)
        if mktcap:
            print(f"  시가총액: {mktcap:,}억원")

    # 추세
    trend = data.get("trend", {})
    if trend:
        print(f"\n[가격 추세]")
        print(f"  최신종가: {trend.get('latest_close', 0):,}원  ({trend.get('latest_date', '')})")
        print(f"  MA5: {trend.get('ma5', '-'):,}  |  MA20: {trend.get('ma20', '-'):,}  |  MA60: {trend.get('ma60', '-') or '-'}")
        print(f"  5일수익률: {trend.get('return_5d', '-')}%  |  20일수익률: {trend.get('return_20d', '-')}%")
        print(f"  60일 고점대비: {trend.get('from_high', '-')}%  |  저점대비: {trend.get('from_low', '-')}%")
        print(f"  거래량비율(vs 20일평균): {trend.get('vol_ratio', '-')}배")

    # 밸류에이션
    val = data.get("valuation", {})
    if val:
        print(f"\n[밸류에이션]")
        print(f"  PER: {val.get('per', '-')}  |  PBR: {val.get('pbr', '-')}")
        print(f"  EPS: {val.get('eps', '-')}  |  BPS: {val.get('bps', '-')}")
        print(f"  외인비율: {val.get('foreign_ratio', '-')}%")

    # 수급
    inv = data.get("investor", {})
    if inv:
        print(f"\n[수급 {inv.get('days', 0)}일 합계]")
        print(f"  외인: {inv.get('foreign_net_total', 0):,}주 ({inv.get('foreign_trend', '')})")
        print(f"  기관: {inv.get('institution_net_total', 0):,}주 ({inv.get('institution_trend', '')})")
        print(f"  개인: {inv.get('individual_net_total', 0):,}주")

    # 재무
    fins = data.get("financials", [])
    if fins:
        print(f"\n[재무제표 최근 {len(fins)}기]")
        for f in fins:
            period = f.get("period", "")
            rev = f.get("revenue", 0)
            op = f.get("oper_profit", 0)
            np = f.get("net_profit", 0)
            roe = f.get("roe", "-")
            print(f"  {period}: 매출 {rev:,}억 | 영업이익 {op:,}억 | 순이익 {np:,}억 | ROE {roe}%")

    # 공매도
    shorts = data.get("short_selling", [])
    if shorts:
        print(f"\n[공매도 최근 {len(shorts)}일]")
        for s in shorts:
            print(f"  {s.get('date', '')}: {s.get('short_volume', 0):,}주 ({s.get('short_ratio', 0):.1f}%)")

    # 뉴스
    news = data.get("naver_news", [])
    if news:
        print(f"\n[네이버 뉴스 최근 {len(news)}건]")
        for n in news:
            dt = n.get("datetime", "")
            # format: YYYYMMDDHHmm -> MM-DD HH:MM
            if len(dt) >= 12:
                dt = f"{dt[4:6]}-{dt[6:8]} {dt[8:10]}:{dt[10:12]}"
            print(f"  [{dt}] {n.get('title', '')} ({n.get('office', '')})")

    # 공시
    disclosures = data.get("disclosures", [])
    if disclosures:
        print(f"\n[공시 최근 {len(disclosures)}건]")
        for d in disclosures:
            dt = d.get("datetime", "")[:10]
            print(f"  [{dt}] {d.get('title', '')}")

    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python stock_analysis.py <종목코드> [종목명]")
        sys.exit(1)

    code = sys.argv[1]
    name = sys.argv[2] if len(sys.argv) > 2 else ""

    data = analyze(code, name)
    print_report(data)

    # JSON 파일로도 저장
    out_dir = Path(__file__).resolve().parent.parent / "data" / "stock-analysis"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{code}_analysis.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    print(f"JSON 저장: {out_file}")

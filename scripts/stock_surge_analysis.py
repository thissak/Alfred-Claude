"""종목 일봉 이상패턴 탐지 + 뉴스 연동 분석 스크립트."""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.kis_readonly_client import get


def fetch_daily_chart(code: str, days: int = 60) -> list[dict]:
    """일봉 데이터 조회."""
    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
    res = get(
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
            parsed.append(
                {
                    "date": item["stck_bsop_date"],
                    "close": int(item["stck_clpr"]),
                    "open": int(item["stck_oprc"]),
                    "high": int(item["stck_hgpr"]),
                    "low": int(item["stck_lwpr"]),
                    "volume": int(item["acml_vol"]),
                }
            )
        except (KeyError, ValueError):
            continue
    return sorted(parsed, key=lambda x: x["date"])


def fetch_investor(code: str) -> list[dict]:
    """투자자별 매매동향 조회."""
    res = get(
        "/uapi/domestic-stock/v1/quotations/inquire-investor",
        "FHKST01010900",
        {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code},
    )
    if not res:
        return []
    items = res.get("output", [])
    parsed = []
    for item in items:
        try:
            parsed.append(
                {
                    "date": item["stck_bsop_date"],
                    "individual": int(item["prsn_ntby_qty"]),
                    "foreign": int(item["frgn_ntby_qty"]),
                    "institution": int(item["orgn_ntby_qty"]),
                }
            )
        except (KeyError, ValueError):
            continue
    return {item["date"]: item for item in parsed}


def fetch_news(code: str, date_from: str, date_to: str) -> list[dict]:
    """종목 뉴스 조회."""
    res = get(
        "/uapi/domestic-stock/v1/quotations/news-title",
        "FHKST01011800",
        {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": code,
            "FID_INPUT_DATE_1": date_from,
            "FID_INPUT_DATE_2": date_to,
            "FID_TITL_CNTT": "",
            "FID_NEWS_OFER_ENTP_CODE": "",
            "FID_COND_MRKT_CLS_CODE": "",
            "FID_INPUT_HOUR_1": "",
            "FID_RANK_SORT_CLS_CODE": "0",
            "FID_INPUT_SRNO": "",
        },
    )
    if not res:
        return []
    items = res.get("output", [])
    parsed = []
    for item in items:
        title = item.get("hts_pbnt_titl_cntt", "")
        if not title:
            continue
        # 인포스탁 순위 기사 필터링
        skip_keywords = ["상위 50종목", "상위 20종목", "신고가 종목", "신저가 종목"]
        if any(kw in title for kw in skip_keywords):
            continue
        parsed.append(
            {
                "date": item.get("data_dt", ""),
                "time": item.get("data_tm", ""),
                "source": item.get("dorg", ""),
                "title": title,
            }
        )
    return sorted(parsed, key=lambda x: x["date"] + x["time"])


def detect_patterns(candles: list[dict]) -> list[dict]:
    """일봉에서 이상 패턴 탐지."""
    if len(candles) < 6:
        return []

    patterns = []
    # 5일 평균 거래량 계산용
    for i in range(5, len(candles)):
        c = candles[i]
        prev = candles[i - 1]

        # 등락률
        if prev["close"] == 0:
            continue
        change_pct = (c["close"] - prev["close"]) / prev["close"] * 100

        # 5일 평균 거래량
        avg_vol_5d = sum(candles[j]["volume"] for j in range(i - 5, i)) / 5
        vol_ratio = c["volume"] / avg_vol_5d if avg_vol_5d > 0 else 0

        # 갭 (시가 vs 전일종가)
        gap_pct = (c["open"] - prev["close"]) / prev["close"] * 100

        # 위꼬리/아래꼬리 비율
        body = abs(c["close"] - c["open"])
        total_range = c["high"] - c["low"]
        if total_range > 0:
            upper_wick = c["high"] - max(c["close"], c["open"])
            lower_wick = min(c["close"], c["open"]) - c["low"]
            upper_wick_ratio = upper_wick / total_range
            lower_wick_ratio = lower_wick / total_range
        else:
            upper_wick_ratio = 0
            lower_wick_ratio = 0

        detected = []

        # 급등 (5%+)
        if change_pct >= 5:
            detected.append(f"급등 {change_pct:+.1f}%")
        # 급락 (-5% 이하)
        elif change_pct <= -5:
            detected.append(f"급락 {change_pct:+.1f}%")

        # 거래량 폭증 (5일 평균 대비 3배+)
        if vol_ratio >= 3:
            detected.append(f"거래량 {vol_ratio:.1f}배")

        # 갭업/갭다운 (3%+)
        if gap_pct >= 3:
            detected.append(f"갭업 {gap_pct:+.1f}%")
        elif gap_pct <= -3:
            detected.append(f"갭다운 {gap_pct:+.1f}%")

        # 장대양봉/장대음봉 (몸통이 전체의 80%+이고 7%+ 변동)
        if total_range > 0 and body / total_range >= 0.7 and abs(change_pct) >= 7:
            if c["close"] > c["open"]:
                detected.append("장대양봉")
            else:
                detected.append("장대음봉")

        # 위꼬리 긴 봉 (상승 시도 후 되밀림)
        if upper_wick_ratio >= 0.6 and total_range > 0:
            detected.append(f"위꼬리 {upper_wick_ratio:.0%}")

        # 아래꼬리 긴 봉 (지지 확인)
        if lower_wick_ratio >= 0.6 and total_range > 0:
            detected.append(f"아래꼬리 {lower_wick_ratio:.0%}")

        if detected:
            patterns.append(
                {
                    "date": c["date"],
                    "close": c["close"],
                    "change_pct": round(change_pct, 2),
                    "volume": c["volume"],
                    "vol_ratio": round(vol_ratio, 1),
                    "gap_pct": round(gap_pct, 2),
                    "patterns": detected,
                }
            )

    return patterns


def analyze(code: str, name: str = "") -> dict:
    """종목 분석 실행."""
    print(f"[1/4] 일봉 조회: {code} {name}")
    candles = fetch_daily_chart(code, days=90)
    if not candles:
        print("  일봉 데이터 없음")
        return {}

    print(f"  → {len(candles)}일 데이터")

    print("[2/4] 이상패턴 탐지")
    patterns = detect_patterns(candles)
    print(f"  → {len(patterns)}건 탐지")

    print("[3/4] 투자자 동향 조회")
    investors = fetch_investor(code)
    print(f"  → {len(investors)}일 데이터")

    print("[4/4] 패턴 날짜별 뉴스 조회")
    for p in patterns:
        news = fetch_news(code, p["date"], p["date"])
        p["news"] = news
        inv = investors.get(p["date"], {})
        p["foreign"] = inv.get("foreign", 0)
        p["institution"] = inv.get("institution", 0)
        p["individual"] = inv.get("individual", 0)
        print(f'  {p["date"]}: {", ".join(p["patterns"])} | 뉴스 {len(news)}건')

    return {
        "code": code,
        "name": name,
        "candle_count": len(candles),
        "period": f'{candles[0]["date"]}~{candles[-1]["date"]}',
        "patterns": patterns,
        "latest": candles[-1] if candles else {},
    }


def format_report(result: dict) -> str:
    """분석 결과를 마크다운 리포트로 포맷."""
    if not result:
        return "데이터 없음"

    lines = []
    lines.append(f'## {result["name"]} ({result["code"]}) 이상패턴 분석')
    lines.append(f'> 분석 기간: {result["period"]} ({result["candle_count"]}일)')
    lines.append(f'> 최종 종가: {result["latest"].get("close", "N/A"):,}원')
    lines.append("")

    if not result["patterns"]:
        lines.append("이상 패턴 없음.")
        return "\n".join(lines)

    lines.append("| 날짜 | 종가 | 등락 | 거래량배율 | 패턴 | 외인 | 기관 | 뉴스 |")
    lines.append("|------|------|------|-----------|------|------|------|------|")

    for p in result["patterns"]:
        news_str = ""
        if p["news"]:
            # 가장 중요한 뉴스 1개 (인포스탁 제외 우선)
            real_news = [n for n in p["news"] if n["source"] != "인포스탁"]
            if real_news:
                news_str = real_news[0]["title"][:40]
            elif p["news"]:
                news_str = p["news"][0]["title"][:40]

        frgn = f'{p["foreign"]:+,}' if p["foreign"] else "-"
        inst = f'{p["institution"]:+,}' if p["institution"] else "-"

        lines.append(
            f'| {p["date"]} | {p["close"]:,} | {p["change_pct"]:+.1f}% | '
            f'{p["vol_ratio"]}x | {", ".join(p["patterns"])} | {frgn} | {inst} | {news_str} |'
        )

    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python stock_surge_analysis.py <종목코드> [종목명]")
        sys.exit(1)

    code = sys.argv[1]
    name = sys.argv[2] if len(sys.argv) > 2 else ""
    result = analyze(code, name)
    print("\n" + "=" * 60)
    print(format_report(result))

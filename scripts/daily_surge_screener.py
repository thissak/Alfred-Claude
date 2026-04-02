"""일별 전종목 이상패턴(surge) 스크리너.

daily_screening 테이블로 1차 필터 → daily_prices로 캔들 패턴 탐지 → 수급 연동.

탐지 패턴:
  급등 +5%  |  급락 -5%  |  거래량폭증 3x  |  갭업/갭다운 3%
  장대양봉/음봉 (몸통70%+변동7%+)  |  꼬리봉 60%+

사용법:
  python3 scripts/daily_surge_screener.py [날짜]    # 기본: DB 최신 날짜
  python3 scripts/daily_surge_screener.py 2026-03-31
"""

import json
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os
os.environ.setdefault("MARKET_DB_HOST", "Ai-Mac-mini.local:8001")
from src.market_db import _query


def fetch_market_returns(date: str) -> dict:
    """당일 시장 지수 등락률 조회."""
    rows = _query(
        "SELECT code, change_rate FROM daily_indices WHERE date = ?", [date]
    )
    result = {}
    for r in rows:
        if r["code"] == "0001":
            result["KOSPI"] = r["change_rate"] or 0
        elif r["code"] == "1001":
            result["KOSDAQ"] = r["change_rate"] or 0
    return result


def fetch_candidates(date: str, min_mktcap: int = 300) -> list[dict]:
    """1차 필터: 거래량 2.5x+ 또는 등락 4%+ 종목."""
    sql = """
    SELECT
        sc.code, s.name, s.market, s.sector, s.mktcap,
        sc.close, sc.per, sc.pbr,
        sc.return_1d, sc.return_5d,
        sc.volume_ratio_5d,
        sc.foreign_net_5d, sc.foreign_net_20d, sc.institution_net_5d,
        sc.foreign_ratio
    FROM daily_screening sc
    JOIN securities s ON sc.code = s.code
    WHERE sc.date = ?
      AND s.mktcap >= ?
      AND s.is_etp = 0 AND s.is_spac = 0 AND s.is_halt = 0 AND s.is_admin = 0
      AND (sc.volume_ratio_5d >= 2.5 OR ABS(sc.return_1d) >= 7.0)
    ORDER BY sc.volume_ratio_5d DESC
    """
    return _query(sql, [date, min_mktcap])


def fetch_candles_batch(codes: list[str], date: str) -> dict[str, list[dict]]:
    """종목들의 최근 2일 OHLCV 조회 (갭/캔들 패턴용)."""
    if not codes:
        return {}
    placeholders = ",".join(["?" for _ in codes])
    sql = f"""
    SELECT code, date, open, high, low, close, volume
    FROM daily_prices
    WHERE code IN ({placeholders})
      AND date <= ?
    ORDER BY code, date DESC
    """
    # 종목당 최근 2일만 필요하지만, 한 번에 가져온 뒤 잘라냄
    rows = _query(sql, codes + [date])

    result = {}
    for r in rows:
        code = r["code"]
        if code not in result:
            result[code] = []
        if len(result[code]) < 2:
            result[code].append(r)
    # 날짜순 정렬 (오래된 것 먼저)
    for code in result:
        result[code].sort(key=lambda x: x["date"])
    return result


def fetch_investor_batch(codes: list[str], date: str) -> dict[str, dict]:
    """종목들의 당일 투자자 수급."""
    if not codes:
        return {}
    placeholders = ",".join(["?" for _ in codes])
    sql = f"""
    SELECT code, foreign_net, institution_net, individual_net
    FROM investor_flow
    WHERE code IN ({placeholders}) AND date = ?
    """
    rows = _query(sql, codes + [date])
    return {r["code"]: r for r in rows}


def detect_patterns_for_day(today: dict, yesterday: Optional[dict],
                            mkt_ret: float = 0.0) -> list[str]:
    """당일 캔들에서 이상 패턴 탐지. mkt_ret=시장 등락률로 보정."""
    patterns = []

    # 등락률 — 시장 보정 (시장 +8%일 때, 종목 +10%면 초과 +2%뿐)
    ret1d = today.get("return_1d")
    if ret1d is not None:
        excess = ret1d - mkt_ret
        # 급등: 시장 대비 +7% 초과 OR 절대 +20%
        if excess >= 7 or ret1d >= 20:
            patterns.append(f"급등 +{ret1d:.1f}%(초과 +{excess:.1f}%)")
        # 급락: 시장 대비 -7% 초과 OR 절대 -20%
        elif excess <= -7 or ret1d <= -20:
            patterns.append(f"급락 {ret1d:.1f}%(초과 {excess:.1f}%)")

    # 거래량 폭증
    vol_ratio = today.get("volume_ratio_5d")
    if vol_ratio is not None and vol_ratio >= 3.0:
        patterns.append(f"거래량 {vol_ratio:.1f}x")

    # 캔들 패턴 (OHLCV 필요)
    o, h, l, c = today.get("open"), today.get("high"), today.get("low"), today.get("close")
    if o and h and l and c and h > l:
        total_range = h - l
        body = abs(c - o)
        change_pct = abs(ret1d) if ret1d else 0

        # 장대양봉/장대음봉 (몸통 70%+, 시장대비 초과변동 7%+)
        excess_abs = abs(ret1d - mkt_ret) if ret1d is not None else change_pct
        if total_range > 0 and body / total_range >= 0.7 and excess_abs >= 7:
            if c > o:
                patterns.append("장대양봉")
            else:
                patterns.append("장대음봉")

        # 위꼬리 긴 봉 (60%+)
        upper_wick = h - max(c, o)
        if total_range > 0 and upper_wick / total_range >= 0.6:
            patterns.append(f"위꼬리 {upper_wick / total_range:.0%}")

        # 아래꼬리 긴 봉 (60%+)
        lower_wick = min(c, o) - l
        if total_range > 0 and lower_wick / total_range >= 0.6:
            patterns.append(f"아래꼬리 {lower_wick / total_range:.0%}")

    # 갭 (전일 종가 vs 당일 시가) — 시장 보정
    if yesterday and o and yesterday.get("close"):
        prev_close = yesterday["close"]
        if prev_close > 0:
            gap_pct = (o - prev_close) / prev_close * 100
            gap_excess = gap_pct - mkt_ret
            # 갭업: 실제 갭업이면서 시장대비 5%+ 초과
            if gap_pct > 0 and gap_excess >= 5:
                patterns.append(f"갭업 +{gap_pct:.1f}%(초과 +{gap_excess:.1f}%)")
            # 갭다운: 실제 갭다운(-3%이하)이거나 시장대비 극단 역행(-8%이하)
            elif gap_pct <= -3:
                patterns.append(f"갭다운 {gap_pct:.1f}%")
            elif gap_excess <= -8:
                patterns.append(f"갭다운 {gap_pct:+.1f}%(시장대비 {gap_excess:.1f}%)")

    return patterns


def screen(target_date: Optional[str] = None, min_mktcap: int = 300) -> tuple:
    """전 종목 surge 스크리닝."""
    if target_date is None:
        rows = _query("SELECT MAX(date) as d FROM daily_screening", [])
        target_date = rows[0]["d"]

    # 시장 등락률 조회 (보정용)
    mkt_rets = fetch_market_returns(target_date)

    candidates = fetch_candidates(target_date, min_mktcap)
    if not candidates:
        return target_date, [], mkt_rets

    codes = [r["code"] for r in candidates]
    candles = fetch_candles_batch(codes, target_date)
    investors = fetch_investor_batch(codes, target_date)

    results = []
    for r in candidates:
        code = r["code"]
        market = r.get("market", "KOSPI")
        mkt_ret = mkt_rets.get(market, 0.0)

        cd = candles.get(code, [])
        today_candle = cd[-1] if cd else {}
        yesterday_candle = cd[-2] if len(cd) >= 2 else None

        # screening 데이터 + candle OHLCV 합치기
        merged = {**r, **today_candle}
        patterns = detect_patterns_for_day(merged, yesterday_candle, mkt_ret)

        if not patterns:
            continue

        inv = investors.get(code, {})
        results.append({
            "code": code,
            "name": r["name"],
            "market": r["market"],
            "sector": r.get("sector", ""),
            "mktcap": r["mktcap"],
            "close": r["close"],
            "return_1d": r.get("return_1d") or 0,
            "return_5d": r.get("return_5d") or 0,
            "volume_ratio_5d": r.get("volume_ratio_5d") or 1.0,
            "per": r.get("per"),
            "pbr": r.get("pbr"),
            "foreign_net_5d": r.get("foreign_net_5d") or 0,
            "institution_net_5d": r.get("institution_net_5d") or 0,
            "foreign_1d": inv.get("foreign_net") or 0,
            "institution_1d": inv.get("institution_net") or 0,
            "patterns": patterns,
        })

    # 패턴 우선순위 정렬: 급등/급락 > 거래량폭증 > 기타
    def sort_key(r):
        has_surge = any("급등" in p or "급락" in p for p in r["patterns"])
        has_vol = any("거래량" in p for p in r["patterns"])
        return (
            -int(has_surge),
            -int(has_vol),
            -abs(r["return_1d"]),
        )

    results.sort(key=sort_key)
    return target_date, results, mkt_rets


def classify_patterns(patterns: list[str]) -> str:
    """패턴 목록을 카테고리로 분류."""
    has_surge_up = any("급등" in p for p in patterns)
    has_surge_down = any("급락" in p for p in patterns)
    has_vol = any("거래량" in p for p in patterns)
    has_gap_up = any("갭업" in p for p in patterns)
    has_gap_down = any("갭다운" in p for p in patterns)

    if has_surge_up and has_vol:
        return "🔴급등+거래량"
    elif has_surge_down and has_vol:
        return "🔵급락+거래량"
    elif has_surge_up:
        return "🔴급등"
    elif has_surge_down:
        return "🔵급락"
    elif has_vol and has_gap_up:
        return "🟡거래량+갭업"
    elif has_vol and has_gap_down:
        return "🟡거래량+갭다운"
    elif has_vol:
        return "🟡거래량폭증"
    elif has_gap_up:
        return "⬆갭업"
    elif has_gap_down:
        return "⬇갭다운"
    return "📊캔들패턴"


def print_report(date: str, results: list[dict], mkt_rets: Optional[dict] = None):
    """스크리닝 결과 리포트."""
    print(f"\n{'='*95}")
    print(f" 일별 이상패턴(Surge) 스크리너 — {date}")
    mkt_str = ""
    if mkt_rets:
        parts = [f"{k} {v:+.1f}%" for k, v in mkt_rets.items()]
        mkt_str = f" | 시장: {', '.join(parts)}"
    print(f" 급등·급락·거래량폭증·갭·장대봉·꼬리봉 (시장보정){mkt_str}")
    print(f"{'='*95}")

    if not results:
        print("  이상패턴 탐지 종목 없음.\n")
        return

    # 카테고리별 집계
    categories = {}
    for r in results:
        cat = classify_patterns(r["patterns"])
        categories.setdefault(cat, []).append(r)

    print(f" 탐지 종목: {len(results)}개\n")

    # 카테고리별 요약
    print(" [카테고리 요약]")
    for cat, items in categories.items():
        print(f"  {cat}: {len(items)}종목")
    print()

    # 상세 테이블 (상위 50개)
    show_n = min(50, len(results))
    print(f" 상위 {show_n}개 표시 (전체 {len(results)}개)\n")

    print(f"  {'분류':12s} | {'종목':14s} {'코드':8s} | {'종가':>8s} {'시총':>6s} | {'1일':>6s} {'5일':>6s} {'거래량':>4s} | {'외인1d':>7s} {'기관1d':>7s} | 패턴")
    print(f"  {'─'*100}")

    for r in results[:show_n]:
        cat = classify_patterns(r["patterns"])
        pattern_str = ", ".join(r["patterns"])
        frgn1d = f"{r['foreign_1d']:+,}" if r["foreign_1d"] else "-"
        inst1d = f"{r['institution_1d']:+,}" if r["institution_1d"] else "-"

        print(
            f"  {cat:12s} | "
            f"{r['name']:14s} {r['code']:8s} | "
            f"{r['close']:>8,} {r['mktcap']:>5,}억 | "
            f"{r['return_1d']:>+5.1f}% {r['return_5d']:>+5.1f}% {r['volume_ratio_5d']:>3.1f}x | "
            f"{frgn1d:>7s} {inst1d:>7s} | "
            f"{pattern_str}"
        )

    # 급등 상위 5개 상세
    surges = [r for r in results if any("급등" in p for p in r["patterns"])]
    if surges:
        print(f"\n{'─'*95}")
        print(f" 급등 종목 상세 (상위 {min(5, len(surges))}개)\n")
        for r in surges[:5]:
            fn5 = r.get("foreign_net_5d", 0)
            ins5 = r.get("institution_net_5d", 0)
            per_str = f"PER {r['per']:.1f}" if r.get("per") else "PER -"
            pbr_str = f"PBR {r['pbr']:.2f}" if r.get("pbr") else "PBR -"

            supply = []
            if fn5 > 0:
                supply.append(f"외인5d 순매수 {fn5:+,}")
            if ins5 > 0:
                supply.append(f"기관5d 순매수 {ins5:+,}")
            if r["foreign_1d"]:
                supply.append(f"외인당일 {r['foreign_1d']:+,}")
            if r["institution_1d"]:
                supply.append(f"기관당일 {r['institution_1d']:+,}")

            print(f"  {r['name']} ({r['code']}) | {r['sector'] or '-'}")
            print(f"    {', '.join(r['patterns'])}")
            print(f"    {per_str} | {pbr_str} | 시총 {r['mktcap']:,}억")
            if supply:
                print(f"    수급: {' | '.join(supply)}")
            print()

    # 급락 상위 5개 상세
    drops = [r for r in results if any("급락" in p for p in r["patterns"])]
    if drops:
        print(f"{'─'*95}")
        print(f" 급락 종목 상세 (상위 {min(5, len(drops))}개)\n")
        for r in drops[:5]:
            fn5 = r.get("foreign_net_5d", 0)
            ins5 = r.get("institution_net_5d", 0)

            supply = []
            if r["foreign_1d"]:
                supply.append(f"외인당일 {r['foreign_1d']:+,}")
            if r["institution_1d"]:
                supply.append(f"기관당일 {r['institution_1d']:+,}")

            print(f"  {r['name']} ({r['code']}) | {r['sector'] or '-'}")
            print(f"    {', '.join(r['patterns'])}")
            print(f"    시총 {r['mktcap']:,}억")
            if supply:
                print(f"    수급: {' | '.join(supply)}")
            print()

    print(f"{'='*95}\n")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    date, results, mkt_rets = screen(target)
    print_report(date, results, mkt_rets)

    # JSON 저장
    out_dir = Path(__file__).resolve().parent.parent / "data"
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / f"daily_surge_{date}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(
            {"date": date, "count": len(results), "results": results},
            f, ensure_ascii=False, indent=2, default=str,
        )
    print(f"JSON 저장: {out_file}")

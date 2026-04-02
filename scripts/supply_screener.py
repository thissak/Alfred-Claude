"""수급 선행 패턴 스크리너 — 외인/기관 본격 출현 + 거래량 급증 종목 발굴 + 점수화.

코오롱티슈진 패턴:
  Phase 1: 거래량만 터짐 (외인/기관 부재)
  Phase 2: 외인/기관이 새로 진입 + 거래량 급증 → 본격 상승  ← 이 시점을 포착

점수 체계 (100점):
  거래량 강도     25점  volume_ratio_5d
  외인 수급 전환  15점  5일 매수 + 이전15일 매도→매수 반전
  기관 수급       15점  5일 순매수 강도 (시총 대비)
  가격 모멘텀     20점  3~10% sweet spot, 과열 감점
  밸류에이션      15점  PER/PBR
  수급 동시성     10점  외인+기관 동시 진입 보너스

감점 필터 (인바이오젠 교훈):
  지분법 의존    -20점  영업적자 + 순이익 흑자 → PER 함정
  매출 빈약     -10점  연매출 100억 미만 → 실체 없는 기업
  거래이력 부족   -8점  MA20 없음 → 거래재개/신규상장 1년 미만
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os
os.environ.setdefault("MARKET_DB_HOST", "Ai-Mac-mini.local:8001")
from src.market_db import _query


# ── 재무 건전성 체크 ──────────────────────────────────────────────

def fetch_financial_flags(codes: list[str]) -> dict[str, dict]:
    """재무 위험 플래그 조회 — 지분법 의존, 매출 빈약 탐지."""
    if not codes:
        return {}

    placeholders = ",".join(["?" for _ in codes])

    # 최신 재무제표
    sql = f"""
    SELECT code, period, revenue, oper_profit, net_profit
    FROM financials
    WHERE code IN ({placeholders})
    ORDER BY code, period DESC
    """
    rows = _query(sql, codes)

    flags = {}
    seen = set()
    for r in rows:
        code = r["code"]
        if code in seen:
            continue
        seen.add(code)

        op = r.get("oper_profit") or 0
        np = r.get("net_profit") or 0
        rev = r.get("revenue") or 0

        f = {}
        # 지분법 의존: 영업적자인데 순이익 흑자 → PER 함정
        if op < 0 and np > 0:
            f["phantom"] = True
        # 매출 빈약: 연매출 100억 미만
        if 0 <= rev < 100:
            f["low_rev"] = True
        # 영업적자
        if op < 0:
            f["oper_loss"] = True

        flags[code] = f

    # 거래이력 조회: 최근 1년 거래일수
    sql2 = f"""
    SELECT code, COUNT(*) as trading_days
    FROM daily_prices
    WHERE code IN ({placeholders})
      AND date >= date('now', '-1 year')
    GROUP BY code
    """
    rows2 = _query(sql2, codes)
    for r in rows2:
        code = r["code"]
        days = r["trading_days"]
        if code not in flags:
            flags[code] = {}
        if days < 120:
            flags[code]["short_history"] = True
            flags[code]["trading_days"] = days

    return flags


# ── 점수 산정 ──────────────────────────────────────────────────

def score_stock(r: dict, fin_flags: dict = None) -> dict:
    """종목별 수급 선행 패턴 점수 (0-100, 감점 시 마이너스 가능)."""
    fn5 = r.get("foreign_net_5d") or 0
    fn20 = r.get("foreign_net_20d") or 0
    ins5 = r.get("institution_net_5d") or 0
    prev_15d = fn20 - fn5
    close = r["close"]
    mktcap_won = r["mktcap"] * 1_0000_0000  # 억 → 원
    vol_ratio = r["volume_ratio_5d"] or 1.0
    ret5 = r["return_5d"] or 0
    per = r.get("per")
    pbr = r.get("pbr")

    s = {}

    # 1. 거래량 강도 (0-25)
    if vol_ratio >= 4.0:
        s["vol"] = 25
    elif vol_ratio >= 3.0:
        s["vol"] = 22
    elif vol_ratio >= 2.5:
        s["vol"] = 19
    elif vol_ratio >= 2.0:
        s["vol"] = 16
    elif vol_ratio >= 1.5:
        s["vol"] = 12
    elif vol_ratio >= 1.3:
        s["vol"] = 8
    else:
        s["vol"] = max(0, int((vol_ratio - 1.0) * 15))

    # 2. 외인 수급 전환 (0-15)
    foreign_value = fn5 * close
    fi = foreign_value / mktcap_won if mktcap_won else 0  # 시총 대비 매수 비율

    if fn5 > 0 and prev_15d <= 0:
        # 핵심 패턴: 이전 매도/무관심 → 매수 전환
        base = min(10, int(fi * 800))
        # 전환 폭이 클수록 가산 (이전 15일 매도량 대비)
        reversal = 5 if prev_15d < 0 and abs(prev_15d) >= fn5 * 0.5 else 3
        s["foreign"] = min(15, base + reversal)
    elif fn5 > 0:
        # 매수 중이지만 전환 패턴은 아님
        s["foreign"] = min(7, int(fi * 400))
    else:
        s["foreign"] = 0

    # 3. 기관 수급 (0-15)
    inst_value = ins5 * close
    ii = inst_value / mktcap_won if mktcap_won else 0

    if ins5 > 0:
        s["inst"] = min(15, int(ii * 800) + 3)
    else:
        s["inst"] = 0

    # 4. 가격 모멘텀 적정성 (0-20) — sweet spot: 3-10%
    if 3 <= ret5 <= 8:
        s["mom"] = 20
    elif 8 < ret5 <= 15:
        s["mom"] = 16
    elif 0 < ret5 < 3:
        s["mom"] = 10
    elif 15 < ret5 <= 25:
        s["mom"] = 11
    elif 25 < ret5 <= 40:
        s["mom"] = 6
    else:
        s["mom"] = 2

    # 5. 밸류에이션 (0-15, 적자 시 -15까지 감점)
    sector = r.get("sector") or ""
    bio_tech = any(k in sector for k in ("제약", "바이오", "의료", "소프트웨어", "IT", "반도체", "일반서비스"))

    v = 7
    if per is not None:
        if per < 0:
            # 적자: 바이오/기술주는 가벼운 감점, 일반업종은 강한 감점
            v = -2 if bio_tech else -15
        elif per < 8:
            v = 15
        elif per < 15:
            v = 12
        elif per < 25:
            v = 9
        elif per < 50:
            v = 6
        else:
            v = 3
    if pbr is not None and 0 < pbr < 1 and (per is None or per > 0):
        v = min(15, v + 3)  # 흑자 저PBR만 가산
    s["val"] = v

    # 6. 수급 동시성 보너스 (0-10)
    if fn5 > 0 and ins5 > 0:
        s["sync"] = 10
    elif fn5 > 0 or ins5 > 0:
        s["sync"] = 3
    else:
        s["sync"] = 0

    # 7. 재무 건전성 감점 (인바이오젠 교훈)
    penalty = 0
    warnings = []
    ff = fin_flags or {}

    if ff.get("phantom"):
        penalty -= 20
        warnings.append("지분법의존")
    if ff.get("low_rev"):
        penalty -= 10
        warnings.append("매출빈약")
    # 거래이력 부족: 최근 1년 거래일 120일 미만 → 거래재개/신규상장
    if ff.get("short_history"):
        penalty -= 8
        days = ff.get("trading_days", 0)
        warnings.append(f"거래이력{days}일")

    s["penalty"] = penalty

    total = sum(s.values())
    return {**s, "total": total, "warnings": warnings}


# ── 시그널 분류 ────────────────────────────────────────────────

def classify_signal(r: dict, min_buy: int = 5000) -> str:
    fn5 = r.get("foreign_net_5d") or 0
    fn20 = r.get("foreign_net_20d") or 0
    ins5 = r.get("institution_net_5d") or 0
    prev_15d = fn20 - fn5

    foreign_new = fn5 >= min_buy and prev_15d <= 0
    foreign_cont = fn5 >= min_buy and prev_15d > 0
    inst_in = ins5 >= min_buy

    if foreign_new and inst_in:
        return "외인전환+기관"
    elif foreign_new:
        return "외인전환"
    elif foreign_cont and inst_in:
        return "외인+기관"
    elif inst_in:
        return "기관진입"
    elif foreign_cont:
        return "외인지속"
    return "-"


# ── 스크리닝 ──────────────────────────────────────────────────

def screen(
    min_vol_ratio: float = 1.2,
    min_return_5d: float = 0.0,
    max_return_5d: float = 50.0,
    min_mktcap: int = 300,
    min_score: int = 40,
    top_n: int = 30,
) -> tuple[str, list[dict]]:
    """수급 본격 출현 스크리닝 + 점수화."""

    rows = _query("SELECT MAX(date) as d FROM daily_screening", [])
    latest_date = rows[0]["d"]

    sql = """
    SELECT
        s.code, s.name, s.market, s.sector, s.mktcap,
        sc.close, sc.per, sc.pbr,
        sc.volume_ratio_5d, sc.return_1d, sc.return_5d,
        sc.foreign_net_5d, sc.foreign_net_20d, sc.institution_net_5d,
        sc.foreign_ratio
    FROM daily_screening sc
    JOIN securities s ON sc.code = s.code
    WHERE sc.date = ?
      AND sc.volume_ratio_5d >= ?
      AND sc.return_5d > ?
      AND sc.return_5d < ?
      AND s.mktcap >= ?
      AND s.sector NOT LIKE 'ETF%'
      AND (sc.foreign_net_5d > 0 OR sc.institution_net_5d > 0)
    ORDER BY sc.volume_ratio_5d DESC
    """

    results = _query(sql, [
        latest_date, min_vol_ratio, min_return_5d, max_return_5d, min_mktcap,
    ])

    # 재무 건전성 플래그 일괄 조회
    all_codes = [dict(r)["code"] for r in results]
    fin_flags = fetch_financial_flags(all_codes)

    scored = []
    for r in results:
        rd = dict(r)
        rd["signal"] = classify_signal(rd)
        rd["foreign_prev_15d"] = (rd.get("foreign_net_20d") or 0) - (rd.get("foreign_net_5d") or 0)
        ff = fin_flags.get(rd["code"], {})
        sc = score_stock(rd, ff)
        rd["scores"] = sc
        rd["total_score"] = sc["total"]
        rd["warnings"] = sc.get("warnings", [])
        scored.append(rd)

    # 점수순 정렬, 최소 점수 필터
    scored = [s for s in scored if s["total_score"] >= min_score]
    scored.sort(key=lambda x: x["total_score"], reverse=True)

    return latest_date, scored[:top_n]


# ── 등급 판정 ─────────────────────────────────────────────────

def grade(score: int) -> str:
    if score >= 75:
        return "A"
    elif score >= 60:
        return "B"
    elif score >= 50:
        return "C"
    return "D"


# ── 출력 ──────────────────────────────────────────────────────

def print_report(date: str, results: list[dict]):
    print(f"\n{'='*90}")
    print(f" 수급 본격 출현 스크리너 — {date}")
    print(f" 거래량급증 + 외인/기관 출현 + 점수 기반 랭킹")
    print(f"{'='*90}")
    print(f" 발굴 종목: {len(results)}개 (40점 이상)\n")

    if not results:
        print("  조건에 맞는 종목이 없습니다.\n")
        return

    # 헤더
    print(f"  {'등급':>2} {'점수':>3} | {'종목':14s} {'코드':8s} | {'종가':>8s} {'시총':>6s} | {'거래량':>4s} {'5일':>6s} | {'외인5d':>8s} {'기관5d':>8s} | {'시그널':10s}")
    print(f"  {'─'*84}")

    for r in results:
        sc = r["total_score"]
        fn5 = r.get("foreign_net_5d") or 0
        ins5 = r.get("institution_net_5d") or 0
        per_str = f"{r['per']:.0f}" if r.get("per") else "-"

        g = grade(sc)
        marker = "★" if g == "A" else "●" if g == "B" else "○"

        warn_str = " ⚠" + ",".join(r.get("warnings", [])) if r.get("warnings") else ""
        print(
            f"  {marker}{g} {sc:>3} | "
            f"{r['name']:14s} {r['code']:8s} | "
            f"{r['close']:>8,} {r['mktcap']:>5,}억 | "
            f"{r['volume_ratio_5d']:>3.1f}x {r['return_5d']:>+5.1f}% | "
            f"{fn5:>+8,} {ins5:>+8,} | "
            f"{r['signal']:10s}{warn_str}"
        )

    # 상세 (상위 10개)
    top = results[:10]
    print(f"\n{'─'*90}")
    print(f" 상위 {len(top)}개 상세 점수 분해\n")

    labels = {"vol": "거래량", "foreign": "외인전환", "inst": "기관", "mom": "모멘텀", "val": "밸류", "sync": "동시성"}
    max_pts = {"vol": 25, "foreign": 15, "inst": 15, "mom": 20, "val": 15, "sync": 10}

    for r in top:
        sc = r["scores"]
        g = grade(r["total_score"])
        fn5 = r.get("foreign_net_5d") or 0
        ins5 = r.get("institution_net_5d") or 0
        prev15 = r.get("foreign_prev_15d", 0)
        warns = r.get("warnings", [])

        warn_tag = f"  ⚠ {','.join(warns)}" if warns else ""
        print(f"  {g} {r['total_score']}점 | {r['name']} ({r['code']}) — {r['signal']}{warn_tag}")

        bar_parts = []
        for key in ["vol", "foreign", "inst", "mom", "val", "sync"]:
            val = sc[key]
            mx = max_pts[key]
            filled = max(0, int(val / mx * 8))
            bar = "█" * filled + "░" * (8 - filled)
            bar_parts.append(f"    {labels[key]:6s} {bar} {val:>3}/{mx}")
        # 감점 표시
        pen = sc.get("penalty", 0)
        if pen < 0:
            bar_parts.append(f"    감점   {'▼' * min(8, abs(pen) // 5):8s} {pen:>3}")
        print("\n".join(bar_parts))

        print(f"    수급: 외인5d {fn5:+,} | 기관5d {ins5:+,} | 외인 이전15d {prev15:+,}")
        per_str = f"PER {r['per']:.1f}" if r.get("per") else "PER -"
        pbr_str = f"PBR {r['pbr']:.2f}" if r.get("pbr") else "PBR -"
        print(f"    밸류: {per_str} | {pbr_str} | 시총 {r['mktcap']:,}억")
        print()

    print(f"{'='*90}\n")


if __name__ == "__main__":
    date, results = screen()
    print_report(date, results)

    # JSON 저장
    out_dir = Path(__file__).resolve().parent.parent / "data"
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / f"supply_screen_{date}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({"date": date, "count": len(results), "results": results},
                  f, ensure_ascii=False, indent=2, default=str)
    print(f"JSON 저장: {out_file}")

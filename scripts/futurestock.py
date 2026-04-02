"""미래주식 — 탑다운 퀀트 스크리닝 시스템.

3단계 탑다운:
  Layer 1: 시장 타이밍 (전종목 정배열 비율 → BUY/CASH)
  Layer 2: 섹터 필터 (섹터별 정배열 비율+모멘텀 → Hot/Cold)
  Layer 3: 종목 선별 (LightGBM 듀얼 모델 → Top N)

Usage:
    python scripts/futurestock.py                    # 오늘 기준 전체 분석
    python scripts/futurestock.py --date 2026-03-28  # 특정일
    python scripts/futurestock.py --top 10           # Top 10만
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import market_db as db

PROJECT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT / "data"
MODEL_CLF = DATA_DIR / "screener_rl_clf.txt"
MODEL_REG = DATA_DIR / "screener_rl_reg.txt"


# ── Layer 1: 시장 타이밍 ─────────────────────────────────

def layer1_market_timing(prices_df, screen_date):
    """전종목 정배열 비율 → 시장 시그널."""
    today = prices_df[(prices_df["date"] == screen_date)].dropna(subset=["ma120"])
    if today.empty:
        return {"signal": "UNKNOWN", "pct_aligned": 0, "detail": "데이터 없음"}

    total = len(today)
    aligned = today["aligned"].sum()
    pct = aligned / total

    # 5일 전 비율 (모멘텀)
    dates = sorted(prices_df["date"].unique())
    sd_idx = dates.index(screen_date) if screen_date in dates else -1
    if sd_idx >= 5:
        d5ago = dates[sd_idx - 5]
        t5 = prices_df[(prices_df["date"] == d5ago)].dropna(subset=["ma120"])
        pct_5ago = t5["aligned"].sum() / len(t5) if len(t5) > 0 else pct
        momentum = pct - pct_5ago
    else:
        momentum = 0

    # 시그널 판정
    if pct < 0.05:
        signal = "BUY"
        state = "바닥 (역발상 매수)"
        color = "🟢"
    elif pct >= 0.25 and pct <= 0.40:
        if momentum > 0:
            signal = "BUY"
            state = "강세 + 가속"
            color = "🟢"
        else:
            signal = "CAUTION"
            state = "강세 + 둔화"
            color = "🟡"
    elif pct > 0.40:
        signal = "CASH"
        state = "과열"
        color = "🔴"
    elif 0.05 <= pct < 0.15:
        signal = "CASH"
        state = "약세"
        color = "🔴"
    else:
        signal = "NEUTRAL"
        state = "보합/전환기"
        color = "⚪"

    return {
        "signal": signal,
        "pct_aligned": round(pct, 4),
        "momentum": round(momentum, 4),
        "total_stocks": total,
        "aligned_stocks": int(aligned),
        "state": state,
        "color": color,
    }


# ── Layer 2: 섹터 필터 ──────────────────────────────────

def layer2_sector_filter(prices_df, screen_date):
    """섹터별 정배열 비율 + 모멘텀 → Hot/Cold 분류."""
    today = prices_df[(prices_df["date"] == screen_date)].dropna(subset=["ma120"])
    if today.empty or "sector" not in today.columns:
        return [], []

    # 섹터별 정배열 비율
    sector_stats = today.groupby("sector").agg(
        total=("code", "count"),
        aligned=("aligned", "sum"),
    ).reset_index()
    sector_stats = sector_stats[sector_stats["total"] >= 10]  # 최소 10종목
    sector_stats["pct_aligned"] = sector_stats["aligned"] / sector_stats["total"]

    # 10일 전 비율 (모멘텀)
    dates = sorted(prices_df["date"].unique())
    sd_idx = dates.index(screen_date) if screen_date in dates else -1
    if sd_idx >= 10:
        d10ago = dates[sd_idx - 10]
        t10 = prices_df[(prices_df["date"] == d10ago)].dropna(subset=["ma120"])
        if not t10.empty and "sector" in t10.columns:
            old_stats = t10.groupby("sector").agg(
                old_total=("code", "count"),
                old_aligned=("aligned", "sum"),
            ).reset_index()
            old_stats["old_pct"] = old_stats["old_aligned"] / old_stats["old_total"]
            sector_stats = sector_stats.merge(old_stats[["sector", "old_pct"]], on="sector", how="left")
            sector_stats["momentum"] = sector_stats["pct_aligned"] - sector_stats["old_pct"].fillna(0)
        else:
            sector_stats["momentum"] = 0
    else:
        sector_stats["momentum"] = 0

    # Hot: 정배열 > 20% & 모멘텀 >= 0
    sector_stats["is_hot"] = (sector_stats["pct_aligned"] > 0.20) & (sector_stats["momentum"] >= 0)

    hot = sector_stats[sector_stats["is_hot"]].sort_values("pct_aligned", ascending=False)
    cold = sector_stats[~sector_stats["is_hot"]].sort_values("pct_aligned", ascending=False)

    return hot.to_dict("records"), cold.to_dict("records")


# ── Layer 3: 종목 선별 ──────────────────────────────────

def layer3_stock_selection(prices_l3, idx_df, val_df, fin_map, screen_date, hot_sectors, top_n=20, prices_with_sector=None):
    """Hot 섹터 내 LightGBM 듀얼 모델 기반 종목 선별."""
    import lightgbm as lgb
    sys.path.insert(0, str(PROJECT / "scripts"))
    from screener_rl import compute_features_batch, FEATURE_COLS, _compute_ev

    feat = compute_features_batch(prices_l3, idx_df, val_df, fin_map, screen_date)
    if feat.empty:
        return []

    # Hot 섹터 필터 (sector 정보는 별도 DataFrame에서)
    if hot_sectors and prices_with_sector is not None:
        today = prices_with_sector[prices_with_sector["date"] == screen_date]
        if "sector" in today.columns:
            hot_codes = set(today[today["sector"].isin(hot_sectors)]["code"])
            if hot_codes:
                feat = feat[feat["code"].isin(hot_codes)]

    if feat.empty:
        return []

    clf = lgb.Booster(model_file=str(MODEL_CLF))
    reg = lgb.Booster(model_file=str(MODEL_REG))

    X = feat[FEATURE_COLS]
    clf_probs = clf.predict(X)
    reg_preds = reg.predict(X)

    feat = feat.copy()
    feat["prob"] = clf_probs
    feat["expected_return"] = reg_preds
    feat["ev"] = _compute_ev(clf_probs, reg_preds)

    # 종목명
    codes = feat["code"].tolist()
    if codes:
        ph = ",".join(["?"] * len(codes))
        names = db._query(f"SELECT code, name, sector FROM securities WHERE code IN ({ph})", codes)
        name_map = {r["code"]: r["name"] for r in names}
        sector_map = {r["code"]: r["sector"] for r in names}
        feat["name"] = feat["code"].map(name_map)
        feat["sector"] = feat["code"].map(sector_map)

    selected = feat.nlargest(min(top_n, len(feat)), "ev")
    return selected.to_dict("records")


# ── 데이터 로드 ──────────────────────────────────────────

def _load_prices_with_sector(start, end):
    """전 종목 일봉 + MA + 섹터."""
    rows = db._query(
        "SELECT dp.code, dp.date, dp.close, dp.volume, dp.change_rate, dp.mktcap, s.sector "
        "FROM daily_prices dp "
        "JOIN securities s ON s.code = dp.code "
        "WHERE dp.date BETWEEN ? AND ? "
        "  AND s.is_etp = 0 AND s.is_spac = 0 AND s.is_halt = 0 AND s.is_admin = 0 "
        "  AND s.sector NOT LIKE 'ETF%%' "
        "  AND dp.volume > 0 AND length(s.code) <= 6 "
        "ORDER BY dp.code, dp.date",
        [start, end],
    )
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    for c in ["close", "volume"]:
        df[c] = df[c].astype(float)
    df["change_rate"] = pd.to_numeric(df["change_rate"], errors="coerce").fillna(0)
    df["mktcap"] = pd.to_numeric(df["mktcap"], errors="coerce").fillna(0)

    df = df.sort_values(["code", "date"]).reset_index(drop=True)
    for w in [5, 20, 60, 120]:
        df[f"ma{w}"] = df.groupby("code")["close"].transform(
            lambda x: x.rolling(w, min_periods=w).mean()
        )
    df["aligned"] = (df["ma5"] > df["ma20"]) & (df["ma20"] > df["ma60"]) & (df["ma60"] > df["ma120"])
    df["semi_aligned"] = (df["ma5"] > df["ma20"]) & (df["ma20"] > df["ma60"]) & (df["ma60"] <= df["ma120"])
    df["vol_ma5"] = df.groupby("code")["volume"].transform(lambda x: x.rolling(5, min_periods=5).mean())
    df["vol_ma20"] = df.groupby("code")["volume"].transform(lambda x: x.rolling(20, min_periods=20).mean())
    return df


# ── 메인 ─────────────────────────────────────────────────

def run(date=None, top_n=20):
    """미래주식 전체 분석."""
    if date is None:
        row = db._query("SELECT MAX(date) d FROM daily_prices")
        date = row[0]["d"]

    print(f"{'='*60}")
    print(f" 미래주식 — {date}")
    print(f"{'='*60}")

    # 데이터 로드
    print("\n데이터 로드 중...")
    prices = _load_prices_with_sector("2021-01-01", date)
    if prices.empty:
        print("데이터 없음")
        return

    # ── Layer 1 ──
    l1 = layer1_market_timing(prices, date)
    print(f"\n{'─'*60}")
    print(f" Layer 1: 시장 타이밍")
    print(f"{'─'*60}")
    print(f"  {l1['color']} 시그널: {l1['signal']} — {l1['state']}")
    print(f"  정배열 비율: {l1['pct_aligned']:.1%} ({l1['aligned_stocks']}/{l1['total_stocks']}종목)")
    print(f"  5일 모멘텀: {l1['momentum']:+.1%}")

    if l1["signal"] == "CASH":
        print(f"\n  ⚠️  현금 보유 권장. 종목 분석 생략.")
        _save_result(date, l1, [], [], [])
        return

    if l1["signal"] == "NEUTRAL":
        print(f"\n  💡 보합 구간 — 종목 분석은 참고용으로 제공합니다.")

    # ── Layer 2 ──
    hot_sectors, cold_sectors = layer2_sector_filter(prices, date)
    print(f"\n{'─'*60}")
    print(f" Layer 2: 섹터 필터")
    print(f"{'─'*60}")

    if hot_sectors:
        print(f"  🔥 Hot 섹터 ({len(hot_sectors)}개):")
        for s in hot_sectors:
            print(f"     {s['sector']:<16} 정배열={s['pct_aligned']:.0%} 모멘텀={s['momentum']:+.1%} ({s['aligned']}/{s['total']}종목)")
    else:
        print(f"  Hot 섹터 없음 — 전 섹터 대상으로 종목 선별")

    if cold_sectors:
        cold_top5 = sorted(cold_sectors, key=lambda x: x["pct_aligned"], reverse=True)[:5]
        print(f"  ❄️  Cold 섹터 상위 5개:")
        for s in cold_top5:
            print(f"     {s['sector']:<16} 정배열={s['pct_aligned']:.0%}")

    # ── Layer 3 ──
    print(f"\n{'─'*60}")
    print(f" Layer 3: 종목 선별 (Top {top_n})")
    print(f"{'─'*60}")

    if not MODEL_CLF.exists() or not MODEL_REG.exists():
        print("  모델 없음. screener_rl.py train을 먼저 실행하세요.")
        _save_result(date, l1, hot_sectors, cold_sectors, [])
        return

    from screener_rl import (
        _load_all_prices as _load_prices_nosector,
        _load_index_ma, _load_valuations_indexed, _load_financials_map,
    )

    prices_l3 = _load_prices_nosector("2021-01-01", date)
    idx = _load_index_ma("2021-01-01", date)
    val = _load_valuations_indexed("2021-01-01", date)
    fin = _load_financials_map()

    hot_names = [s["sector"] for s in hot_sectors] if hot_sectors else []
    picks = layer3_stock_selection(prices_l3, idx, val, fin, date, hot_names, top_n, prices)

    if picks:
        print(f"\n  {'코드':<8} {'종목명':<14} {'섹터':<14} {'EV':>6} {'P(수익)':>7} {'E[수익]':>7} {'정배열':>5}")
        print(f"  {'─'*65}")
        for p in picks:
            ev = p.get("ev", 0)
            conv = "★★★" if ev >= 0.03 else ("★★" if ev >= 0.015 else "★")
            print(f"  {p['code']:<8} {p.get('name','?'):<14} {p.get('sector','?'):<14} "
                  f"{ev:5.3f} {p['prob']:6.0%} {p['expected_return']:+6.1%} "
                  f"{int(p.get('alignment_days',0)):4d}일 {conv}")
    else:
        print("  선별 종목 없음")

    # 저장
    _save_result(date, l1, hot_sectors, cold_sectors, picks)
    print(f"\n{'='*60}")
    print(f" 분석 완료: {date}")
    print(f"{'='*60}")


def _save_result(date, l1, hot, cold, picks):
    """결과 JSON 저장."""
    result = {
        "date": date,
        "layer1": l1,
        "layer2": {
            "hot_sectors": hot,
            "cold_sectors": cold[:5] if cold else [],
        },
        "layer3": [{
            "code": p["code"],
            "name": p.get("name", ""),
            "sector": p.get("sector", ""),
            "ev": round(p.get("ev", 0), 4),
            "prob": round(p.get("prob", 0), 3),
            "expected_return": round(p.get("expected_return", 0), 4),
            "alignment_days": int(p.get("alignment_days", 0)),
        } for p in picks],
    }
    out = DATA_DIR / "futurestock_latest.json"
    with open(out, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n  저장: {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="미래주식 — 탑다운 퀀트 스크리닝")
    parser.add_argument("--date", default=None)
    parser.add_argument("--top", type=int, default=20)
    args = parser.parse_args()
    run(args.date, args.top)

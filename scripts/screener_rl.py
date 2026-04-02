"""정배열 유지 예측 — LightGBM 분류기 기반 스크리너.

Usage:
    python scripts/screener_rl.py build-dataset          # 피처+라벨 구축
    python scripts/screener_rl.py train                   # walk-forward CV + 모델 저장
    python scripts/screener_rl.py backtest                # 전 기간 백테스트
    python scripts/screener_rl.py screen [--date 2026-03-28]  # 스크리닝
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
MODEL_CLF_PATH = DATA_DIR / "screener_rl_clf.txt"
MODEL_REG_PATH = DATA_DIR / "screener_rl_reg.txt"
DATASET_PATH = DATA_DIR / "screener_rl_dataset.csv.gz"


# ── 데이터 로드 ──────────────────────────────────────────

def _load_all_prices(start, end):
    """전 종목 일봉 + MA 사전계산."""
    rows = db._query(
        "SELECT dp.code, dp.date, dp.close, dp.volume, dp.change_rate, dp.mktcap "
        "FROM daily_prices dp "
        "JOIN securities s ON s.code = dp.code "
        "WHERE dp.date BETWEEN ? AND ? "
        "  AND s.is_etp = 0 AND s.is_spac = 0 AND s.is_halt = 0 AND s.is_admin = 0 "
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

    # MA 사전계산 (벡터화)
    df = df.sort_values(["code", "date"]).reset_index(drop=True)
    for w in [5, 20, 60, 120]:
        df[f"ma{w}"] = df.groupby("code")["close"].transform(
            lambda x: x.rolling(w, min_periods=w).mean()
        )
    df["aligned"] = (df["ma5"] > df["ma20"]) & (df["ma20"] > df["ma60"]) & (df["ma60"] > df["ma120"])
    df["semi_aligned"] = (df["ma5"] > df["ma20"]) & (df["ma20"] > df["ma60"]) & (df["ma60"] <= df["ma120"])

    # 볼륨 MA
    df["vol_ma5"] = df.groupby("code")["volume"].transform(lambda x: x.rolling(5, min_periods=5).mean())
    df["vol_ma20"] = df.groupby("code")["volume"].transform(lambda x: x.rolling(20, min_periods=20).mean())

    return df


def _load_index_ma(start, end, code="0001"):
    """KOSPI 지수 MA20/MA60."""
    rows = db._query(
        "SELECT date, close FROM daily_indices WHERE code=? AND date BETWEEN ? AND ?",
        [code, start, end],
    )
    df = pd.DataFrame(rows).sort_values("date")
    if df.empty:
        return df
    df["close"] = df["close"].astype(float)
    df["kospi_ma20"] = df["close"].rolling(20, min_periods=20).mean()
    df["kospi_ma60"] = df["close"].rolling(60, min_periods=60).mean()
    df["kospi_regime"] = (df["kospi_ma20"] - df["kospi_ma60"]) / df["kospi_ma60"]
    df["kospi_ret_20d"] = df["close"].pct_change(20)
    return df.set_index("date")[["kospi_regime", "kospi_ret_20d"]]


def _load_valuations_indexed(start, end):
    """밸류에이션 → (code, date) 인덱스."""
    rows = db._query(
        "SELECT code, date, per, pbr, foreign_ratio FROM daily_valuations WHERE date BETWEEN ? AND ?",
        [start, end],
    )
    df = pd.DataFrame(rows)
    for c in ["per", "pbr", "foreign_ratio"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def _load_financials_map():
    """종목별 최신 재무 → dict."""
    rows = db._query(
        "SELECT code, roe, net_profit, oper_profit_growth "
        "FROM financials WHERE period_type='annual' ORDER BY code, period DESC"
    )
    df = pd.DataFrame(rows)
    if df.empty:
        return {}
    df = df.drop_duplicates(subset="code", keep="first")
    return df.set_index("code").to_dict("index")


# ── 피처 계산 (벡터화) ───────────────────────────────────

def compute_features_batch(prices_df, idx_df, val_df, fin_map, screen_date):
    """screen_date 기준 피처. 정배열/준정배열 종목만."""
    # screen_date 행 추출
    today = prices_df[prices_df["date"] == screen_date].copy()
    if today.empty:
        return pd.DataFrame()

    # MA120 존재 = 120일 이상 데이터 있음
    today = today.dropna(subset=["ma120"])
    # 정배열 or 준정배열만
    today = today[today["aligned"] | today["semi_aligned"]].copy()
    if today.empty:
        return pd.DataFrame()

    codes = today["code"].unique()

    # ── MA Health ──
    today["spread_5_20"] = (today["ma5"] - today["ma20"]) / today["ma20"]
    today["spread_20_60"] = (today["ma20"] - today["ma60"]) / today["ma60"]
    today["spread_60_120"] = (today["ma60"] - today["ma120"]) / today["ma120"]
    today["ma_uniformity"] = today[["spread_5_20", "spread_20_60", "spread_60_120"]].std(axis=1)
    today["close_vs_ma5"] = (today["close"] - today["ma5"]) / today["ma5"]
    today["close_vs_ma20"] = (today["close"] - today["ma20"]) / today["ma20"]

    # alignment_days — 연속 정배열 일수 (per code)
    aligned_series = prices_df[prices_df["code"].isin(codes) & (prices_df["date"] <= screen_date)].copy()
    aligned_series = aligned_series.sort_values(["code", "date"])

    def _count_trailing_aligned(g):
        vals = g["aligned"].values
        count = 0
        for v in reversed(vals):
            if v:
                count += 1
            else:
                break
        return count

    adays = aligned_series.groupby("code").apply(_count_trailing_aligned, include_groups=False).rename("alignment_days")
    today = today.merge(adays, left_on="code", right_index=True, how="left")
    today["alignment_days"] = today["alignment_days"].fillna(0).astype(int)

    # ── Momentum — 과거 N일 수익률 ──
    hist = prices_df[prices_df["code"].isin(codes) & (prices_df["date"] <= screen_date)].copy()
    hist = hist.sort_values(["code", "date"])

    def _momentum_feats(g):
        g = g.sort_values("date")
        c = g["close"].values
        if len(c) < 61:
            return pd.Series({"ret_5d": np.nan, "ret_20d": np.nan, "ret_60d": np.nan,
                              "volatility_20d": np.nan, "max_dd_20d": np.nan})
        ret_5d = c[-1] / c[-6] - 1 if c[-6] != 0 else 0
        ret_20d = c[-1] / c[-21] - 1 if c[-21] != 0 else 0
        ret_60d = c[-1] / c[-61] - 1 if c[-61] != 0 else 0
        rets = np.diff(c[-21:]) / c[-21:-1]
        vol = rets.std()
        peak = np.maximum.accumulate(c[-21:])
        dd = (c[-21:] - peak) / np.where(peak != 0, peak, 1)
        return pd.Series({"ret_5d": ret_5d, "ret_20d": ret_20d, "ret_60d": ret_60d,
                          "volatility_20d": vol, "max_dd_20d": dd.min()})

    mom = hist.groupby("code").apply(_momentum_feats, include_groups=False)
    today = today.merge(mom, left_on="code", right_index=True, how="left")

    # ── Volume ──
    today["vol_ratio_5d"] = today["vol_ma5"] / today["vol_ma20"].replace(0, np.nan)

    def _vol_trend(g):
        g = g.sort_values("date")
        v = g["volume"].values[-20:]
        if len(v) < 20:
            return np.nan
        avg = v.mean()
        if avg == 0:
            return 0
        v_norm = v / avg
        return np.polyfit(np.arange(20), v_norm, 1)[0]

    vtrend = hist.groupby("code").apply(_vol_trend, include_groups=False).rename("vol_trend_20d")
    today = today.merge(vtrend, left_on="code", right_index=True, how="left")

    # ── Valuation ──
    val_today = val_df[val_df["date"] == screen_date].drop_duplicates(subset="code")
    if not val_today.empty:
        today = today.merge(val_today[["code", "per", "pbr", "foreign_ratio"]], on="code", how="left")
    else:
        today["per"], today["pbr"], today["foreign_ratio"] = np.nan, np.nan, np.nan

    # foreign_ratio 20일 변화
    val_20d = val_df[val_df["code"].isin(codes)].copy()
    if not val_20d.empty:
        val_20d = val_20d.sort_values(["code", "date"])
        val_latest = val_20d.drop_duplicates(subset="code", keep="last")[["code", "foreign_ratio"]].rename(
            columns={"foreign_ratio": "fr_now"})
        # 20일 전 (대략)
        dates_before = val_20d["date"].unique()
        dates_before = sorted(dates_before)
        idx_20 = max(0, len(dates_before) - 21)
        date_20ago = dates_before[idx_20]
        val_old = val_20d[val_20d["date"] == date_20ago].drop_duplicates(subset="code")[["code", "foreign_ratio"]].rename(
            columns={"foreign_ratio": "fr_old"})
        fr_chg = val_latest.merge(val_old, on="code", how="left")
        fr_chg["foreign_ratio_chg_20d"] = fr_chg["fr_now"] - fr_chg["fr_old"]
        today = today.merge(fr_chg[["code", "foreign_ratio_chg_20d"]], on="code", how="left")
    else:
        today["foreign_ratio_chg_20d"] = np.nan

    # ── Fundamentals ──
    today["roe"] = today["code"].map(lambda c: fin_map.get(c, {}).get("roe", np.nan))
    today["oper_profit_growth"] = today["code"].map(lambda c: fin_map.get(c, {}).get("oper_profit_growth", np.nan))
    today["has_profit"] = today["code"].map(lambda c: 1 if (fin_map.get(c, {}).get("net_profit") or 0) > 0 else 0)

    # ── Market regime ──
    if not idx_df.empty and screen_date in idx_df.index:
        today["kospi_regime"] = idx_df.loc[screen_date, "kospi_regime"]
        today["kospi_ret_20d"] = idx_df.loc[screen_date, "kospi_ret_20d"]
    else:
        today["kospi_regime"], today["kospi_ret_20d"] = np.nan, np.nan

    today["is_aligned"] = today["aligned"].astype(int)

    cols = ["code", "date"] + FEATURE_COLS
    # 없는 컬럼 채우기
    for c in cols:
        if c not in today.columns:
            today[c] = np.nan

    return today[cols].copy()


def compute_labels_batch(prices_df, screen_date, horizon=20):
    """screen_date 이후 horizon일 정배열 유지율. 벡터화."""
    future_dates = sorted(prices_df[prices_df["date"] > screen_date]["date"].unique())[:horizon]
    if len(future_dates) < horizon:
        return pd.DataFrame()

    # 각 future date에서 aligned 여부
    future = prices_df[prices_df["date"].isin(future_dates)][["code", "date", "aligned"]].copy()
    # 종목별 정배열 일수
    label = future.groupby("code")["aligned"].agg(
        alignment_count="sum", total="count"
    ).reset_index()
    label["alignment_ratio"] = (label["alignment_count"] / horizon).round(3)
    label["maintained"] = (label["alignment_ratio"] >= 0.8).astype(int)

    # forward return
    sd_prices = prices_df[prices_df["date"] == screen_date][["code", "close"]].rename(columns={"close": "close_sd"})
    last_date = future_dates[-1]
    end_prices = prices_df[prices_df["date"] == last_date][["code", "close"]].rename(columns={"close": "close_end"})
    ret = sd_prices.merge(end_prices, on="code")
    ret["forward_return"] = ((ret["close_end"] / ret["close_sd"]) - 1).round(4)

    label = label.merge(ret[["code", "forward_return"]], on="code", how="left")
    return label[["code", "alignment_ratio", "maintained", "forward_return"]]


# ── 피처 컬럼 ─────────────────────────────────────────────

FEATURE_COLS = [
    "is_aligned", "spread_5_20", "spread_20_60", "spread_60_120",
    "ma_uniformity", "alignment_days", "close_vs_ma5", "close_vs_ma20",
    "ret_5d", "ret_20d", "ret_60d", "volatility_20d", "max_dd_20d",
    "vol_ratio_5d", "vol_trend_20d",
    "per", "pbr", "foreign_ratio", "foreign_ratio_chg_20d",
    "roe", "oper_profit_growth", "has_profit",
    "kospi_regime", "kospi_ret_20d", "mktcap",
]


# ── 데이터셋 빌드 ────────────────────────────────────────

def build_dataset():
    """전 기간 피처+라벨 구축."""
    rows = db._query("""
        SELECT date FROM (
            SELECT date, ROW_NUMBER() OVER (PARTITION BY substr(date,1,7) ORDER BY date) rn
            FROM (SELECT DISTINCT date FROM daily_prices WHERE date BETWEEN '2022-07-01' AND '2025-09-30')
        ) WHERE rn=1 ORDER BY date
    """)
    screen_dates = [r["date"] for r in rows]
    print(f"스크리닝 날짜: {len(screen_dates)}개 ({screen_dates[0]} ~ {screen_dates[-1]})")

    print("데이터 로드 중...")
    prices = _load_all_prices("2022-01-01", "2025-12-31")
    idx = _load_index_ma("2022-01-01", "2025-12-31")
    val = _load_valuations_indexed("2022-01-01", "2025-12-31")
    fin = _load_financials_map()
    print(f"  prices: {len(prices):,} rows, MA 사전계산 완료")

    all_rows = []
    for i, sd in enumerate(screen_dates):
        print(f"[{i+1}/{len(screen_dates)}] {sd} ...", end=" ", flush=True)

        feat = compute_features_batch(prices, idx, val, fin, sd)
        if feat.empty:
            print("0종목")
            continue

        labels = compute_labels_batch(prices, sd)
        if labels.empty:
            print("라벨 부족")
            continue

        feat = feat.merge(labels, on="code", how="inner")
        all_rows.append(feat)
        print(f"{len(feat)}종목 (유지: {int(feat['maintained'].sum())})")

    dataset = pd.concat(all_rows, ignore_index=True)
    dataset.to_csv(DATASET_PATH, index=False, compression="gzip")
    print(f"\n데이터셋 저장: {DATASET_PATH}")
    print(f"총 {len(dataset):,}행, 유지율: {dataset['maintained'].mean():.1%}")
    return dataset


# ── 모델 학습 (듀얼: 분류 + 회귀) ─────────────────────────

CLF_PARAMS = {
    "objective": "binary", "metric": "auc",
    "learning_rate": 0.05, "num_leaves": 31, "max_depth": 6,
    "min_child_samples": 50, "subsample": 0.8, "colsample_bytree": 0.8,
    "reg_alpha": 0.1, "reg_lambda": 0.1, "verbose": -1,
}

REG_PARAMS = {
    "objective": "huber", "metric": "mae", "alpha": 0.9,  # huber: 이상치에 강건
    "learning_rate": 0.05, "num_leaves": 31, "max_depth": 6,
    "min_child_samples": 50, "subsample": 0.8, "colsample_bytree": 0.8,
    "reg_alpha": 0.1, "reg_lambda": 0.1, "verbose": -1,
}


def _compute_ev(clf_prob, reg_pred):
    """복합 스코어: P(수익) × E[수익률]. 음수 기대수익은 0으로."""
    ev = clf_prob * np.maximum(reg_pred, 0)
    return ev


def train_model(dataset=None):
    """듀얼 모델 walk-forward CV + 저장."""
    import lightgbm as lgb
    from sklearn.metrics import precision_score, recall_score, roc_auc_score

    if dataset is None:
        dataset = pd.read_csv(DATASET_PATH)

    dataset = dataset.sort_values("date").reset_index(drop=True)
    # 라벨: 양수 수익 여부
    dataset["profitable"] = (dataset["forward_return"] > 0).astype(int)
    # 수익률 clipping (극단값 방지)
    dataset["return_clipped"] = dataset["forward_return"].clip(-0.3, 0.5)

    print(f"학습 데이터: {len(dataset):,}행")
    print(f"양수 수익 비율: {dataset['profitable'].mean():.1%}")
    print(f"평균 수익률: {dataset['forward_return'].mean():.3f}\n")

    folds = [
        ("2022-07-01", "2024-06-30", "2024-07-01", "2024-09-30"),
        ("2022-07-01", "2024-09-30", "2024-10-01", "2024-12-31"),
        ("2022-07-01", "2024-12-31", "2025-01-01", "2025-03-31"),
        ("2022-07-01", "2025-03-31", "2025-04-01", "2025-06-30"),
        ("2022-07-01", "2025-06-30", "2025-07-01", "2025-09-30"),
    ]

    print(f"{'Fold':<6} {'기간':>22} {'n':>5} {'CLF AUC':>8} {'Top20 수익':>10} {'Top20 승률':>10} {'전체 평균':>10}")
    print("─" * 75)

    for i, (tr_s, tr_e, va_s, va_e) in enumerate(folds):
        train = dataset[(dataset["date"] >= tr_s) & (dataset["date"] <= tr_e)]
        val = dataset[(dataset["date"] >= va_s) & (dataset["date"] <= va_e)]
        if val.empty or train.empty:
            continue

        X_tr, X_va = train[FEATURE_COLS], val[FEATURE_COLS]

        # 분류기: 양수 수익 예측
        dtrain_c = lgb.Dataset(X_tr, label=train["profitable"])
        dval_c = lgb.Dataset(X_va, label=val["profitable"], reference=dtrain_c)
        clf = lgb.train(CLF_PARAMS, dtrain_c, num_boost_round=500,
                        valid_sets=[dval_c],
                        callbacks=[lgb.early_stopping(30), lgb.log_evaluation(0)])

        # 회귀: 수익률 예측
        dtrain_r = lgb.Dataset(X_tr, label=train["return_clipped"])
        dval_r = lgb.Dataset(X_va, label=val["return_clipped"], reference=dtrain_r)
        reg = lgb.train(REG_PARAMS, dtrain_r, num_boost_round=500,
                        valid_sets=[dval_r],
                        callbacks=[lgb.early_stopping(30), lgb.log_evaluation(0)])

        # 복합 스코어 → 날짜별 Top 20 성능
        clf_probs = clf.predict(X_va)
        reg_preds = reg.predict(X_va)
        val = val.copy()
        val["ev"] = _compute_ev(clf_probs, reg_preds)
        val["clf_prob"] = clf_probs

        auc = roc_auc_score(val["profitable"], clf_probs) if val["profitable"].nunique() > 1 else 0

        # 날짜별 Top 20 선별 후 실제 수익률
        top_returns = []
        top_wins = []
        for _, dg in val.groupby("date"):
            top = dg.nlargest(20, "ev")
            top_returns.append(top["forward_return"].mean())
            top_wins.append((top["forward_return"] > 0).mean())

        avg_ret = np.mean(top_returns)
        avg_win = np.mean(top_wins)
        all_ret = val["forward_return"].mean()

        print(f"{i+1:<6} {va_s}~{va_e} {len(val):5d} {auc:8.3f} {avg_ret:+9.1%} {avg_win:10.1%} {all_ret:+9.1%}")

    # 최종 모델 저장
    print("\n최종 모델 학습 (전체)...")
    X_all = dataset[FEATURE_COLS]
    clf_final = lgb.train(CLF_PARAMS, lgb.Dataset(X_all, label=dataset["profitable"]),
                          num_boost_round=300)
    reg_final = lgb.train(REG_PARAMS, lgb.Dataset(X_all, label=dataset["return_clipped"]),
                          num_boost_round=300)
    clf_final.save_model(str(MODEL_CLF_PATH))
    reg_final.save_model(str(MODEL_REG_PATH))
    print(f"분류 모델: {MODEL_CLF_PATH}")
    print(f"회귀 모델: {MODEL_REG_PATH}")

    # 피처 중요도 (회귀 모델 기준 — 수익률 예측에 뭐가 중요한지)
    imp = pd.Series(
        reg_final.feature_importance(importance_type="gain"),
        index=FEATURE_COLS,
    ).sort_values(ascending=False)
    print("\n수익률 예측 피처 중요도 (top 10):")
    for name, val in imp.head(10).items():
        print(f"  {name:<25} {val:.0f}")

    return clf_final, reg_final


# ── 백테스트 (수익률 기반) ────────────────────────────────

def backtest(top_n=20):
    """Walk-forward 백테스트. 날짜별 Top N 선별 → 실제 수익률 측정."""
    import lightgbm as lgb

    dataset = pd.read_csv(DATASET_PATH)
    dataset = dataset.sort_values("date").reset_index(drop=True)
    dataset["profitable"] = (dataset["forward_return"] > 0).astype(int)
    dataset["return_clipped"] = dataset["forward_return"].clip(-0.3, 0.5)
    dates = sorted(dataset["date"].unique())

    min_train = 12
    results = []

    print(f"백테스트: Top {top_n} 선별, {len(dates)}개 날짜\n")
    print(f"{'날짜':>10} {'후보':>4} {'선별':>4} {'평균수익':>8} {'승률':>6} {'최대수익':>8} {'최대손실':>8}")
    print("─" * 60)

    for i, sd in enumerate(dates):
        if i < min_train:
            continue

        train = dataset[dataset["date"] < sd]
        test = dataset[dataset["date"] == sd]
        if train.empty or test.empty:
            continue

        X_tr, X_te = train[FEATURE_COLS], test[FEATURE_COLS]

        # 분류기
        clf = lgb.train(CLF_PARAMS, lgb.Dataset(X_tr, label=train["profitable"]),
                        num_boost_round=200)
        # 회귀
        reg = lgb.train(REG_PARAMS, lgb.Dataset(X_tr, label=train["return_clipped"]),
                        num_boost_round=200)

        clf_probs = clf.predict(X_te)
        reg_preds = reg.predict(X_te)

        test = test.copy()
        test["ev"] = _compute_ev(clf_probs, reg_preds)
        test["clf_prob"] = clf_probs
        test["reg_pred"] = reg_preds

        # Top N 선별
        top = test.nlargest(min(top_n, len(test)), "ev")
        avg_ret = top["forward_return"].mean()
        win_rate = (top["forward_return"] > 0).mean()
        max_gain = top["forward_return"].max()
        max_loss = top["forward_return"].min()
        all_avg = test["forward_return"].mean()

        results.append({
            "date": sd, "total": len(test), "selected": len(top),
            "avg_return": round(avg_ret, 4),
            "win_rate": round(win_rate, 3),
            "max_gain": round(max_gain, 4),
            "max_loss": round(max_loss, 4),
            "universe_avg": round(all_avg, 4),
            "alpha": round(avg_ret - all_avg, 4),
        })
        print(f"{sd} {len(test):4d} {len(top):4d} {avg_ret:+7.1%} {win_rate:5.0%} "
              f"{max_gain:+7.1%} {max_loss:+7.1%}  (전체:{all_avg:+.1%})")

    rdf = pd.DataFrame(results)
    avg_ret = rdf["avg_return"].mean()
    avg_win = rdf["win_rate"].mean()
    avg_alpha = rdf["alpha"].mean()
    cumulative = (1 + rdf["avg_return"]).prod() - 1

    print(f"\n{'='*60}")
    print(f"백테스트 요약: {len(results)}개월, Top {top_n}")
    print(f"평균 월수익률:     {avg_ret:+.2%}")
    print(f"평균 승률:         {avg_win:.1%}")
    print(f"평균 알파 (vs 전체): {avg_alpha:+.2%}")
    print(f"누적 수익률:       {cumulative:+.1%}")
    print(f"{'='*60}")

    out = DATA_DIR / "screener_rl_backtest.json"
    with open(out, "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"저장: {out}")


# ── 스크리닝 ──────────────────────────────────────────────

def screen(date=None, top_n=20):
    """특정일 스크리닝. 듀얼 모델 기반."""
    import lightgbm as lgb

    if not MODEL_CLF_PATH.exists() or not MODEL_REG_PATH.exists():
        print("모델 없음. 먼저 train을 실행하세요.")
        return

    clf = lgb.Booster(model_file=str(MODEL_CLF_PATH))
    reg = lgb.Booster(model_file=str(MODEL_REG_PATH))

    if date is None:
        row = db._query("SELECT MAX(date) d FROM daily_prices")
        date = row[0]["d"]

    print(f"스크리닝: {date}")
    prices = _load_all_prices("2021-01-01", date)
    idx = _load_index_ma("2021-01-01", date)
    val = _load_valuations_indexed("2021-01-01", date)
    fin = _load_financials_map()

    feat = compute_features_batch(prices, idx, val, fin, date)
    if feat.empty:
        print("정배열/준정배열 종목 없음")
        return

    X = feat[FEATURE_COLS]
    clf_probs = clf.predict(X)
    reg_preds = reg.predict(X)

    feat["prob"] = clf_probs
    feat["expected_return"] = reg_preds
    feat["ev"] = _compute_ev(clf_probs, reg_preds)
    feat["conviction"] = feat["ev"].apply(_conviction_ev)
    feat["score"] = (feat["ev"] * 1000).round(0).astype(int)  # EV를 스코어화

    codes = feat["code"].tolist()
    if codes:
        ph = ",".join(["?"] * len(codes))
        names = db._query(f"SELECT code, name FROM securities WHERE code IN ({ph})", codes)
        name_map = {r["code"]: r["name"] for r in names}
        feat["name"] = feat["code"].map(name_map)

    selected = feat.nlargest(top_n, "ev")

    print(f"\n후보 {len(feat)}종목 중 Top {len(selected)} 선별:\n")
    print(f"  {'코드':<8} {'종목명':<12} {'Conv':<7} {'EV':>5} {'P(수익)':>7} {'E[수익]':>7} {'정배열':>5}")
    print("  " + "─" * 55)
    for _, row in selected.iterrows():
        print(f"  {row['code']:<8} {row.get('name','?'):<12} "
              f"{row['conviction']:<7} {row['score']:5.0f} "
              f"{row['prob']:6.0%} {row['expected_return']:+6.1%} "
              f"{int(row['alignment_days']):4d}일")

    output = []
    for _, row in selected.iterrows():
        output.append({
            "code": row["code"], "name": row.get("name", ""),
            "conviction": row["conviction"],
            "score": int(row["score"]),
            "prob_profitable": round(float(row["prob"]), 3),
            "expected_return": round(float(row["expected_return"]), 4),
            "ev": round(float(row["ev"]), 4),
            "alignment_days": int(row["alignment_days"]),
        })
    out_file = DATA_DIR / "screener_rl_picks.json"
    with open(out_file, "w") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n저장: {out_file}")


def _conviction_ev(ev):
    """EV 기반 conviction. EV = P(수익) × E[수익률]."""
    if ev >= 0.03:
        return "high"
    elif ev >= 0.015:
        return "medium"
    elif ev >= 0.005:
        return "low"
    return "skip"


# ── CLI ───────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="정배열 스크리너 — LightGBM")
    sub = parser.add_subparsers(dest="mode", required=True)
    sub.add_parser("build-dataset", help="피처+라벨 구축")
    sub.add_parser("train", help="walk-forward 학습")
    sub.add_parser("backtest", help="전 기간 백테스트")
    p_screen = sub.add_parser("screen", help="스크리닝")
    p_screen.add_argument("--date", default=None)

    args = parser.parse_args()
    if args.mode == "build-dataset":
        build_dataset()
    elif args.mode == "train":
        train_model()
    elif args.mode == "backtest":
        backtest()
    elif args.mode == "screen":
        screen(args.date)

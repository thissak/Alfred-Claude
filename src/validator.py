"""validator.py — 예측 검증 + 팩터 가중치 자동 조정."""

import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import market_db as db

MIN_SAMPLES = 20
LEARNING_RATE = 0.1
MIN_WEIGHT = 5
MAX_WEIGHT = 40


def evaluate_matured():
    """timeframe 지난 pending 예측 검증."""
    conn = db._get_conn()
    pending = conn.execute(
        "SELECT * FROM predictions WHERE result='pending'"
    ).fetchall()

    evaluated = []
    for p in pending:
        prices = conn.execute(
            "SELECT date, close, high, low FROM daily_prices "
            "WHERE code=? AND date > ? ORDER BY date ASC LIMIT ?",
            (p["code"], p["date"], p["timeframe"]),
        ).fetchall()

        if len(prices) < p["timeframe"]:
            continue

        exit_price = prices[-1]["close"]
        max_price = max(pr["high"] for pr in prices)
        min_price = min(pr["low"] for pr in prices)
        entry = p["entry_price"]
        return_pct = round((exit_price - entry) / entry * 100, 2)

        if max_price >= p["target_price"]:
            result = "hit_target"
        elif min_price <= p["stop_price"]:
            result = "hit_stop"
        elif return_pct > 0:
            result = "neutral_up"
        else:
            result = "neutral_down"

        conn.execute(
            """UPDATE predictions SET exit_price=?, max_price=?, min_price=?,
               result=?, return_pct=?, evaluated_at=datetime('now','localtime')
               WHERE id=?""",
            (exit_price, max_price, min_price, result, return_pct, p["id"]),
        )
        evaluated.append({
            "code": p["code"], "result": result,
            "return_pct": return_pct,
            "factor_scores": json.loads(p["factor_scores"]),
        })

    conn.commit()
    return evaluated


def update_factor_stats(evaluated):
    """팩터별 적중 통계 갱신."""
    conn = db._get_conn()
    for ev in evaluated:
        is_hit = ev["result"] in ("hit_target", "neutral_up")
        for factor, score in ev["factor_scores"].items():
            if score < 10:
                continue
            conn.execute(
                """INSERT INTO factor_stats (factor, period, hit_count, miss_count, avg_contribution)
                   VALUES (?, 'all', ?, ?, ?)
                   ON CONFLICT(factor, period) DO UPDATE SET
                       hit_count = hit_count + ?,
                       miss_count = miss_count + ?,
                       updated_at = datetime('now','localtime')""",
                (factor,
                 1 if is_hit else 0, 0 if is_hit else 1, score,
                 1 if is_hit else 0, 0 if is_hit else 1),
            )
    conn.commit()


def update_weights():
    """적중률 기반 가중치 조정."""
    conn = db._get_conn()
    total = conn.execute(
        "SELECT COUNT(*) as n FROM predictions WHERE result != 'pending'"
    ).fetchone()["n"]

    if total < MIN_SAMPLES:
        return None

    from predictor import get_weights
    current = get_weights()

    stats = conn.execute(
        "SELECT factor, hit_count, miss_count FROM factor_stats WHERE period='all'"
    ).fetchall()
    if not stats:
        return None

    hit_rates = {}
    for s in stats:
        t = s["hit_count"] + s["miss_count"]
        if t >= 5:
            hit_rates[s["factor"]] = s["hit_count"] / t

    if not hit_rates:
        return None

    avg_rate = sum(hit_rates.values()) / len(hit_rates)
    new_weights = current.copy()

    for factor, rate in hit_rates.items():
        if factor not in new_weights:
            continue
        delta = (rate - avg_rate) * 100 * LEARNING_RATE
        new_weights[factor] = max(MIN_WEIGHT, min(MAX_WEIGHT, new_weights[factor] + delta))

    total_w = sum(new_weights.values())
    new_weights = {k: round(v / total_w * 100, 1) for k, v in new_weights.items()}

    accuracy = conn.execute(
        """SELECT ROUND(100.0 * SUM(CASE WHEN result IN ('hit_target','neutral_up')
           THEN 1 ELSE 0 END) / COUNT(*), 1)
           FROM predictions WHERE result != 'pending'"""
    ).fetchone()[0]

    conn.execute(
        "INSERT INTO scoring_weights (date, weights, accuracy, sample_size) VALUES (?, ?, ?, ?)",
        (datetime.now().strftime("%Y-%m-%d"), json.dumps(new_weights), accuracy, total),
    )
    conn.commit()
    return new_weights


def run_daily_validation():
    """일일 검증 파이프라인."""
    evaluated = evaluate_matured()
    if evaluated:
        update_factor_stats(evaluated)
    new_weights = update_weights()
    return {"evaluated": len(evaluated), "new_weights": new_weights}

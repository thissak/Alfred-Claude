"""predictor.py — 급등 후 눌림목 예측 스코어링 (v4).

4대 축: 기술적(25) + 재료소화(30) + 수급(25) + 펀더멘탈(20) = 100점
v4 추가: 거래량 선행 시그널 감점, 밸류트랩 감점
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import market_db as db

INITIAL_WEIGHTS = {
    "tech": 25, "catalyst": 30, "supply": 25, "fundamental": 20,
}
BUY_THRESHOLD = 65
WATCH_THRESHOLD = 50
TARGET_PCT = 10.0
STOP_PCT = -5.0
TIMEFRAME = 5


def get_weights():
    rows = db._query(
        "SELECT weights FROM scoring_weights ORDER BY version DESC LIMIT 1"
    )
    if rows:
        return json.loads(rows[0]["weights"])
    return INITIAL_WEIGHTS.copy()


def score_stock(code, date):
    """단일 종목 v3 스코어링. 급등 후 눌림 구간인 종목만 대상."""
    # 최근 5일 가격
    prices = db._query(
        "SELECT date, close, high, volume, change_rate FROM daily_prices "
        "WHERE code=? AND date<=? ORDER BY date DESC LIMIT 6", [code, date]
    )
    if len(prices) < 4:
        return None

    today = prices[0]
    close = today["close"]
    if not close:
        return None

    # 최근 5일 내 급등(+10%) 있었나 체크
    surge_day = None
    for p in prices[1:]:
        if p["change_rate"] and p["change_rate"] >= 10:
            surge_day = p
            break
    if not surge_day:
        return None

    # 눌림 계산
    recent_high = max(p["high"] for p in prices if p["high"])
    pullback = (close - recent_high) / recent_high * 100 if recent_high else 0
    if pullback > -2 or pullback < -20:
        return None

    # 스크리닝 데이터
    scr = db._query(
        "SELECT * FROM daily_screening WHERE code=? AND date=?", [code, date]
    )
    if not scr:
        return None
    s = scr[0]

    # 수급
    flow_total = db._query(
        "SELECT SUM(foreign_net) as fn, SUM(institution_net) as inst "
        "FROM investor_flow WHERE code=? AND date BETWEEN ? AND ?",
        [code, surge_day["date"], date]
    )
    flow_today = db._query(
        "SELECT foreign_net as fn, institution_net as inst "
        "FROM investor_flow WHERE code=? AND date=?", [code, date]
    )
    fn_total = (flow_total[0]["fn"] or 0) if flow_total else 0
    inst_total = (flow_total[0]["inst"] or 0) if flow_total else 0
    fn_today = (flow_today[0]["fn"] or 0) if flow_today else 0
    inst_today = (flow_today[0]["inst"] or 0) if flow_today else 0

    # 재무
    fin = db._query(
        "SELECT net_profit, roe FROM financials WHERE code=? "
        "ORDER BY period DESC LIMIT 1", [code]
    )
    fi = fin[0] if fin else {}
    profit = (fi.get("net_profit") or 0) > 0
    roe = fi.get("roe") or 0

    # 밸류에이션
    val = db._query(
        "SELECT per, pbr FROM daily_valuations WHERE code=? AND date=?",
        [code, date]
    )
    v = val[0] if val else {}

    # 뉴스
    news = db._query(
        "SELECT COUNT(*) as cnt FROM news WHERE code=? "
        "AND date BETWEEN ? AND ?", [code, surge_day["date"], date]
    )
    nc = (news[0]["cnt"] if news else 0) or 0
    new_news = db._query(
        "SELECT COUNT(*) as cnt FROM news WHERE code=? "
        "AND date > ? AND date <= ?", [code, surge_day["date"], date]
    )
    new_nc = (new_news[0]["cnt"] if new_news else 0) or 0

    # 거래량 감소율
    surge_vol = surge_day["volume"] or 1
    today_vol = today["volume"] or 0
    vol_decay = today_vol / surge_vol

    ma20 = s.get("ma20") or 0
    above_ma20 = close > ma20 if ma20 else False
    ret_20d = s.get("return_20d") or 0
    sr = surge_day["change_rate"]

    # === v3 스코어링 ===

    # 1. 기술적 (25점)
    tech = 0
    if -10 <= pullback <= -5:
        tech += 10
    elif -15 <= pullback < -5:
        tech += 7
    elif -5 < pullback <= -3:
        tech += 5
    if vol_decay < 0.3:
        tech += 8
    elif vol_decay < 0.5:
        tech += 6
    elif vol_decay < 0.7:
        tech += 3
    if above_ma20:
        tech += 4
    if 5 <= ret_20d <= 20:
        tech += 3
    elif 0 < ret_20d < 5:
        tech += 2
    elif ret_20d > 30:
        tech -= 2

    # 2. 재료 소화도 (30점)
    catalyst = 15
    if 10 <= sr < 15:
        catalyst += 8
    elif 15 <= sr < 20:
        catalyst += 3
    elif sr >= 20:
        catalyst -= 5
    if nc == 0:
        # v4: 뉴스 0건 + 급등 = 거래량 선행 (재료 불명 = 리스크)
        if sr >= 10:
            catalyst -= 5  # 재료 없이 급등 → 감점
        else:
            catalyst += 5
    elif 1 <= nc <= 3:
        catalyst += 7
    elif 4 <= nc <= 8:
        catalyst += 2
    elif nc > 8:
        catalyst -= 5
    if new_nc >= 1:
        catalyst += 3
    catalyst = max(0, min(30, catalyst))

    # 3. 수급 (25점) — 눌림 당일 방향 + 전환
    supply = 10
    if fn_today > 0 and inst_today > 0:
        supply += 10
    elif fn_today > 0:
        supply += 5
    elif inst_today > 0:
        supply += 4
    elif fn_today < 0 and inst_today < 0:
        supply -= 5
    if fn_total < 0 and fn_today > 0:
        supply += 5
    if inst_total < 0 and inst_today > 0:
        supply += 3
    if fn_total + inst_total > 1000000:
        supply -= 3
    supply = max(0, min(25, supply))

    # 4. 펀더멘탈 (20점)
    fundamental = 5
    if profit:
        fundamental += 8
    if roe > 10:
        fundamental += 4
    elif roe > 0:
        fundamental += 2
    elif roe < -20:
        fundamental -= 3
    per = v.get("per") or 0
    if 0 < per <= 15:
        fundamental += 3
    elif 0 < per <= 30:
        fundamental += 1
    elif per > 100:
        fundamental -= 2

    # v4: 밸류트랩 감점 — 저PER인데 영업이익 감소 추세
    if fi:
        op_growth = fi.get("oper_profit_growth")
        if op_growth is not None and op_growth < -10 and per and 0 < per < 10:
            fundamental -= 5  # 저PER + 이익감소 = 밸류트랩
        # 영업이익 연속 감소 추가 체크
        fins_hist = db._query(
            "SELECT oper_profit_growth FROM financials WHERE code=? "
            "AND period_type='quarterly' ORDER BY period DESC LIMIT 3", [code]
        )
        declining = sum(1 for f2 in fins_hist
                        if f2.get("oper_profit_growth") is not None
                        and f2["oper_profit_growth"] < 0)
        if declining >= 2:
            fundamental -= 3  # 2분기 이상 연속 감소

    fundamental = max(0, min(20, fundamental))

    total = tech + catalyst + supply + fundamental
    signal = "buy" if total >= BUY_THRESHOLD else (
        "watch" if total >= WATCH_THRESHOLD else "skip"
    )

    return {
        "code": code,
        "date": date,
        "score": total,
        "signal": signal,
        "entry_price": close,
        "target_price": int(close * (1 + TARGET_PCT / 100)),
        "stop_price": int(close * (1 + STOP_PCT / 100)),
        "timeframe": TIMEFRAME,
        "factor_scores": json.dumps({
            "tech": tech, "catalyst": catalyst,
            "supply": supply, "fundamental": fundamental,
        }),
    }


def run_daily_prediction(date):
    """전 종목 스크리닝 → 눌림목 예측 기록."""
    codes = db.get_active_codes()
    results = []
    for code in codes:
        r = score_stock(code, date)
        if r and r["signal"] != "skip":
            db.upsert_prediction(r)
            results.append(r)
    return results

#!/usr/bin/env python3
"""미국 10년물 국채금리(^TNX) 데이터 소스 — 야후 파이낸스 chart API.

야후 비공식 chart API를 urllib로 직접 호출 (API 키·라이브러리 불필요).
- fetch_history(): 일봉 전체 [(date, yield)] — 백필용 (period1/period2)
- fetch_quote():   현재값/전일대비/52주 — 보고·페이지용 (meta + 일봉 직전종가)

^TNX는 yield 그대로 (4.552 = 4.552%). 변동 1bp = 0.01%p.
FRED/stooq는 맥프로에서 timeout/봇차단으로 탈락 → 야후 단일 소스.
"""

import json
import time
import urllib.request
from datetime import datetime

_BASE = "https://query1.finance.yahoo.com/v8/finance/chart/%5ETNX"  # ^TNX
_UA = {"User-Agent": "Mozilla/5.0"}


def _get_json(url, timeout=20):
    try:
        req = urllib.request.Request(url, headers=_UA)
        return json.loads(urllib.request.urlopen(req, timeout=timeout).read())
    except Exception:
        return None


def _result(data):
    """chart.result[0] 안전 추출. 실패/에러 시 None."""
    try:
        res = data["chart"]["result"][0]
        return None if res.get("error") else res
    except (KeyError, IndexError, TypeError):
        return None


def _series(res):
    """res → [(date('YYYY-MM-DD'), close)] 오름차순, null 제외. 빈/이상 시 []."""
    try:
        ts = res["timestamp"]
        gm = res["meta"].get("gmtoffset", 0)
        closes = res["indicators"]["quote"][0]["close"]
    except (KeyError, IndexError, TypeError):
        return []
    out = []
    for t, c in zip(ts, closes):
        if c is None:
            continue
        d = datetime.utcfromtimestamp(t + gm).strftime("%Y-%m-%d")
        out.append((d, round(float(c), 4)))
    return out


def fetch_history():
    """^TNX 일봉 전체 → [(date, yield)] 오름차순 (1970~). 실패 시 None."""
    data = _get_json(f"{_BASE}?period1=0&period2={int(time.time())}&interval=1d", timeout=25)
    res = _result(data) if data else None
    if not res:
        return None
    return _series(res) or None


def fetch_quote():
    """현재 금리 스냅샷. Returns dict|None:
       {price, prev_close, change_bp, w52_high, w52_low, market_time}.
       전일대비는 meta.chartPreviousClose(범위 시작 직전)가 아니라
       일봉 직전 거래일 종가로 계산 (장중/마감 모두 정확)."""
    data = _get_json(f"{_BASE}?range=1mo&interval=1d", timeout=15)
    res = _result(data) if data else None
    if not res:
        return None
    m = res.get("meta", {})
    price = m.get("regularMarketPrice")
    series = _series(res)  # [(date, close)]
    if price is None or len(series) < 2:
        return None
    price = round(float(price), 4)
    gm = m.get("gmtoffset", 0)
    mt = m.get("regularMarketTime")
    today = (datetime.utcfromtimestamp(mt + gm).strftime("%Y-%m-%d")
             if mt else series[-1][0])
    # 오늘 진행봉을 제외한 직전 거래일 종가
    prev_close = next((c for d, c in reversed(series) if d < today), series[-2][1])
    return {
        "price": price,
        "prev_close": prev_close,
        "change_bp": round((price - prev_close) * 100, 1),
        "w52_high": m.get("fiftyTwoWeekHigh"),
        "w52_low": m.get("fiftyTwoWeekLow"),
        "market_time": mt,
        "as_of": today,   # 미 거래일 (gmtoffset 반영) — daily_indices 날짜 키
    }

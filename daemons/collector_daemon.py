#!/usr/bin/env python3
"""주식 데이터 일일 수집 데몬 — 장 마감 후 전 종목 수집.

수집 스케줄 (평일):
  15:45  마스터파일 갱신 → securities
  15:45  시장 지수      → daily_indices (KOSPI/KOSDAQ/KOSPI200)
  15:50  전종목 현재가  → daily_prices + daily_valuations
  16:05  전종목 수급    → investor_flow
  16:20  스크리닝 지표  → daily_screening
  16:30  급등 뉴스 스크리닝 → surge_alerts
  16:35  관심종목+급등종목 뉴스 → news
  16:40  예측 검증 (5일 전 예측 vs 실제)
  16:41  눌림목 예측 스코어링 → predictions

환경변수:
  KIS_THROTTLE=0.067   (15 RPS, 기본 0.5)
  COLLECTOR_RUN_NOW=1   (즉시 1회 실행, 테스트용)
"""

import os
import sys
import time
import traceback
from datetime import datetime, timedelta

# 프로젝트 루트 설정
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "skills", "stock"))
sys.path.insert(0, os.path.join(ROOT, "skills", "stock", "screener_v2"))

# KIS 쓰로틀 설정 (기본 0.5 → 수집기는 15 RPS)
os.environ.setdefault("KIS_THROTTLE", "0.067")

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))

import market_db as db
from screener import _download_master, _parse_master
from kis_endpoints import fetch_kr_price_detail, fetch_kr_investor
from kis_readonly_client import get as kis_get
from normalize import _safe_int, _safe_float
from monitor_base import MonitorBase

sys.path.insert(0, os.path.join(ROOT, "scripts"))
from scan_surge import scan_eod, log as surge_log


# ── 마스터파일 갱신 ─────────────────────────────────────

def refresh_master():
    """마스터파일 다운로드 → securities 테이블 갱신. Returns: 종목 수."""
    total = 0
    for market, part2_len in [("kospi", 228), ("kosdaq", 222)]:
        market_upper = market.upper()
        try:
            mst_path = _download_master(market)
            stocks = _parse_master(mst_path, part2_len=part2_len)
        except Exception as e:
            log(f"마스터파일 {market} 실패: {e}")
            continue

        rows = [
            {
                "code": s["code"],
                "name": s["name"],
                "market": market_upper,
                "sector": None,
                "is_etp": 1 if s["etp"] == "Y" else 0,
                "is_spac": 1 if s["spac"] == "Y" else 0,
                "is_halt": 1 if s["trading_halt"] in ("Y", "1") else 0,
                "is_admin": 1 if s["admin"] in ("Y", "1") else 0,
                "mktcap": s["mktcap"],
            }
            for s in stocks
        ]
        n = db.upsert_securities(rows)
        log(f"{market_upper}: {n}종목 갱신")
        total += n
    return total


# ── 시장 지수 수집 ────────────────────────────────────

INDICES = [
    ("0001", "KOSPI"),
    ("1001", "KOSDAQ"),
    ("2001", "KOSPI200"),
]


def scan_indices(date_str=None):
    """KOSPI/KOSDAQ/KOSPI200 지수 → daily_indices. Returns: 건수."""
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")

    rows = []
    for code, name in INDICES:
        data = kis_get(
            "/uapi/domestic-stock/v1/quotations/inquire-index-price",
            "FHPUP02100000",
            {"FID_COND_MRKT_DIV_CODE": "U", "FID_INPUT_ISCD": code},
        )
        if not data:
            log(f"지수 {name} 수집 실패")
            continue

        o = data["output"]
        rows.append({
            "code": code,
            "name": name,
            "date": date_str,
            "close": _safe_float(o.get("bstp_nmix_prpr")),
            "change": _safe_float(o.get("bstp_nmix_prdy_vrss")),
            "change_rate": _safe_float(o.get("bstp_nmix_prdy_ctrt")),
            "volume": _safe_int(o.get("acml_vol")),
            "trade_value": _safe_int(o.get("acml_tr_pbmn")),
        })

    if rows:
        n = db.upsert_daily_indices(rows)
        log(f"지수 완료: {n}건 ({', '.join(r['name'] for r in rows)})")
    return len(rows)


# ── 전종목 현재가 수집 ──────────────────────────────────

def scan_prices(date_str=None):
    """전종목 inquire-price → daily_prices + daily_valuations. Returns: 건수."""
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")

    codes = db.get_active_codes()
    log(f"현재가 수집 시작: {len(codes)}종목")

    price_rows = []
    val_rows = []
    errors = 0

    for i, code in enumerate(codes):
        output = fetch_kr_price_detail(code)
        if not output:
            errors += 1
            continue

        price_rows.append({
            "code": code,
            "date": date_str,
            "open": _safe_int(output.get("stck_oprc")),
            "high": _safe_int(output.get("stck_hgpr")),
            "low": _safe_int(output.get("stck_lwpr")),
            "close": _safe_int(output.get("stck_prpr")) or 0,
            "volume": _safe_int(output.get("acml_vol")),
            "trade_value": _safe_int(output.get("acml_tr_pbmn")),
            "mktcap": _safe_int(output.get("hts_avls")),
            "change_rate": _safe_float(output.get("prdy_ctrt")),
        })

        val_rows.append({
            "code": code,
            "date": date_str,
            "per": _safe_float(output.get("per")),
            "pbr": _safe_float(output.get("pbr")),
            "eps": _safe_float(output.get("eps")),
            "bps": _safe_float(output.get("bps")),
            "foreign_ratio": _safe_float(output.get("hts_frgn_ehrt")),
        })

        if (i + 1) % 500 == 0:
            log(f"  현재가 {i+1}/{len(codes)} ({errors} errors)")

    n1 = db.upsert_daily_prices(price_rows)
    n2 = db.upsert_daily_valuations(val_rows)
    log(f"현재가 완료: {n1} prices, {n2} valuations ({errors} errors)")
    return n1


# ── 전종목 수급 수집 ────────────────────────────────────

def scan_investor_flow():
    """전종목 투자자 매매동향 30일 → investor_flow. Returns: 건수."""
    codes = db.get_active_codes()
    log(f"수급 수집 시작: {len(codes)}종목")

    all_rows = []
    errors = 0

    for i, code in enumerate(codes):
        data = fetch_kr_investor(code)
        if not data:
            errors += 1
            continue

        for item in data:
            date_raw = item.get("stck_bsop_date", "")
            if not date_raw or len(date_raw) != 8:
                continue
            date_str = f"{date_raw[:4]}-{date_raw[4:6]}-{date_raw[6:8]}"

            frgn = item.get("frgn_ntby_qty", "")
            orgn = item.get("orgn_ntby_qty", "")
            prsn = item.get("prsn_ntby_qty", "")
            if not frgn and not orgn and not prsn:
                continue

            all_rows.append({
                "code": code,
                "date": date_str,
                "foreign_net": int(frgn) if frgn else 0,
                "institution_net": int(orgn) if orgn else 0,
                "individual_net": int(prsn) if prsn else 0,
            })

        if (i + 1) % 500 == 0:
            log(f"  수급 {i+1}/{len(codes)} ({errors} errors)")

    n = db.insert_investor_flow(all_rows)
    log(f"수급 완료: {n}건 ({errors} errors)")
    return n


# ── 스크리닝 지표 계산 ──────────────────────────────────

def compute_screening(date_str=None):
    """daily_prices + daily_valuations + investor_flow → daily_screening."""
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")

    conn = db._get_conn()
    codes = db.get_active_codes()
    log(f"스크리닝 계산 시작: {len(codes)}종목")

    rows = []
    for code in codes:
        # 최근 120일 종가
        prices = conn.execute(
            "SELECT date, close, volume FROM daily_prices "
            "WHERE code=? AND date<=? ORDER BY date DESC LIMIT 120",
            (code, date_str),
        ).fetchall()

        if not prices or prices[0]["date"] != date_str:
            continue

        closes = [p["close"] for p in prices if p["close"]]
        volumes = [p["volume"] for p in prices if p["volume"]]

        if not closes:
            continue

        close = closes[0]

        def ma(n):
            return sum(closes[:n]) / n if len(closes) >= n else None

        def ret(n):
            return (closes[0] / closes[n] - 1) * 100 if len(closes) > n and closes[n] else None

        vol_avg_5 = sum(volumes[:5]) / 5 if len(volumes) >= 5 else None
        vol_ratio = volumes[0] / vol_avg_5 if vol_avg_5 and volumes else None

        # 밸류에이션
        val = conn.execute(
            "SELECT per, pbr, foreign_ratio FROM daily_valuations "
            "WHERE code=? AND date=?", (code, date_str),
        ).fetchone()

        # 시총
        price_row = conn.execute(
            "SELECT mktcap FROM daily_prices WHERE code=? AND date=?",
            (code, date_str),
        ).fetchone()

        # 수급 누적
        flow_5 = conn.execute(
            "SELECT SUM(foreign_net) as f, SUM(institution_net) as i "
            "FROM (SELECT foreign_net, institution_net FROM investor_flow "
            "      WHERE code=? AND date<=? ORDER BY date DESC LIMIT 5)",
            (code, date_str),
        ).fetchone()

        flow_20 = conn.execute(
            "SELECT SUM(foreign_net) as f "
            "FROM (SELECT foreign_net FROM investor_flow "
            "      WHERE code=? AND date<=? ORDER BY date DESC LIMIT 20)",
            (code, date_str),
        ).fetchone()

        rows.append({
            "code": code,
            "date": date_str,
            "close": close,
            "mktcap": price_row["mktcap"] if price_row else None,
            "per": val["per"] if val else None,
            "pbr": val["pbr"] if val else None,
            "ma5": ma(5),
            "ma20": ma(20),
            "ma60": ma(60),
            "ma120": ma(120),
            "return_1d": ret(1),
            "return_5d": ret(5),
            "return_20d": ret(20),
            "return_60d": ret(60),
            "volume_ratio_5d": round(vol_ratio, 2) if vol_ratio else None,
            "foreign_net_5d": flow_5["f"] if flow_5 else None,
            "foreign_net_20d": flow_20["f"] if flow_20 else None,
            "institution_net_5d": flow_5["i"] if flow_5 else None,
            "foreign_ratio": val["foreign_ratio"] if val else None,
        })

    if rows:
        n = db.upsert_daily_screening(rows)
        log(f"스크리닝 완료: {n}종목")
    else:
        log("스크리닝: 데이터 없음")
    return len(rows)


# ── 급등 뉴스 스크리닝 ──────────────────────────────────

def scan_surge_alerts(date_str=None):
    """급등 종목 추출 + 뉴스 조회 → surge_alerts."""
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")
    try:
        alerts = scan_eod(date_str, min_return=5.0, min_vol_ratio=1.5)
        log(f"급등 스크리닝 완료: {len(alerts)}건")
    except Exception as e:
        log(f"급등 스크리닝 실패: {e}")


# ── 뉴스 수집 ──────────────────────────────────────────

def scan_news(date_str=None):
    """관심종목 + 당일 급등종목 뉴스 수집 → news 테이블. Returns: 건수."""
    import json
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")
    date_raw = date_str.replace("-", "")

    # 관심종목 로드
    config_path = os.path.join(ROOT, "skills", "stock", "config.json")
    codes = set()
    try:
        with open(config_path) as f:
            config = json.load(f)
        wl = config.get("watchlist", [])
        if isinstance(wl, list):
            for item in wl:
                if isinstance(item, dict):
                    codes.add(item.get("code", ""))
        elif isinstance(wl, dict):
            for cat in wl.values():
                if isinstance(cat, list):
                    for item in cat:
                        if isinstance(item, dict):
                            codes.add(item.get("code", ""))
    except Exception:
        pass

    # 당일 급등종목 추가
    try:
        alerts = db.get_surge_alerts(date=date_str, min_return=5.0, limit=50)
        for a in alerts:
            codes.add(a["code"])
    except Exception:
        pass

    codes.discard("")
    log(f"뉴스 수집 시작: {len(codes)}종목")

    skip_keywords = ["상위 50종목", "상위 20종목", "신고가 종목", "신저가 종목"]
    all_rows = []
    for code in codes:
        try:
            res = kis_get(
                "/uapi/domestic-stock/v1/quotations/news-title",
                "FHKST01011800",
                {
                    "FID_COND_MRKT_DIV_CODE": "J",
                    "FID_INPUT_ISCD": code,
                    "FID_INPUT_DATE_1": date_raw,
                    "FID_INPUT_DATE_2": date_raw,
                    "FID_TITL_CNTT": "",
                    "FID_NEWS_OFER_ENTP_CODE": "",
                    "FID_COND_MRKT_CLS_CODE": "",
                    "FID_INPUT_HOUR_1": "",
                    "FID_RANK_SORT_CLS_CODE": "0",
                    "FID_INPUT_SRNO": "",
                },
            )
            if not res:
                continue
            for item in res.get("output") or []:
                title = item.get("hts_pbnt_titl_cntt", "")
                if not title or any(kw in title for kw in skip_keywords):
                    continue
                dt = item.get("data_dt", "")
                if len(dt) == 8:
                    dt = f"{dt[:4]}-{dt[4:6]}-{dt[6:8]}"
                tm = item.get("data_tm", "")
                if len(tm) == 6:
                    tm = f"{tm[:2]}:{tm[2:4]}:{tm[4:6]}"
                all_rows.append({
                    "code": code,
                    "date": dt,
                    "time": tm,
                    "title": title,
                    "source": item.get("dorg", ""),
                })
        except Exception:
            continue

    if all_rows:
        n = db.upsert_news(all_rows)
        log(f"뉴스 완료: {n}건 ({len(codes)}종목)")
    else:
        log("뉴스: 데이터 없음")
    return len(all_rows)


# ── 일일 수집 오케스트레이션 ────────────────────────────

def run_daily_collection():
    """전체 일일 수집 파이프라인 실행."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    log(f"=== 일일 수집 시작 ({date_str}) ===")

    t0 = time.time()

    refresh_master()
    scan_indices(date_str)
    scan_prices(date_str)
    scan_investor_flow()
    compute_screening(date_str)
    scan_surge_alerts(date_str)
    scan_news(date_str)

    # 예측 피드백 루프
    try:
        from validator import run_daily_validation
        from predictor import run_daily_prediction

        val = run_daily_validation()
        log(f"검증: {val['evaluated']}건, weights={'updated' if val['new_weights'] else 'unchanged'}")

        preds = run_daily_prediction(date_str)
        buy_cnt = sum(1 for p in preds if p["signal"] == "buy")
        log(f"예측: {len(preds)}건 ({buy_cnt} buy, {len(preds)-buy_cnt} watch)")
    except Exception as e:
        log(f"예측 루프 에러: {e}")

    elapsed = time.time() - t0
    log(f"=== 일일 수집 완료 ({elapsed:.0f}초) ===")


class CollectorDaemon(MonitorBase):
    name = "collector"
    interval = 30
    weekday_only = True

    def on_start(self):
        db.init()
        self._triggered = False

    def check(self):
        hm = datetime.now().hour * 100 + datetime.now().minute
        if hm < 100:
            self._triggered = False
        if 1545 <= hm <= 1550 and not self._triggered:
            self._triggered = True
            run_daily_collection()
            return "수집 완료"
        return f"대기 (triggered={self._triggered})"


# collector 내부에서 쓰는 log 함수 — 기존 파이프라인 함수들이 참조
def log(msg):
    print(f"[collector {datetime.now():%H:%M:%S}] {msg}", flush=True)


if __name__ == "__main__":
    CollectorDaemon().run()

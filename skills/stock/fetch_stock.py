#!/usr/bin/env python3
"""주식 데이터 수집 → data/stock.json"""

import os
import sys
import json
import time
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

# 프로젝트 루트 기준
ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(ROOT / ".env")

APP_KEY = os.getenv("KIS_APP_KEY")
APP_SECRET = os.getenv("KIS_APP_SECRET")
ACCOUNT = os.getenv("KIS_ACCOUNT")
BASE_URL = "https://openapi.koreainvestment.com:9443"
TOKEN_PATH = ROOT / "run" / "kis_token.json"
DATA_PATH = ROOT / "data" / "stock.json"
CONFIG_PATH = ROOT / "skills" / "stock" / "config.json"
REPORT_REPO = Path("/tmp/stock-report")


# --- 토큰 관리 ---

def _get_token():
    """캐싱된 토큰 반환. 만료 시 재발급."""
    if TOKEN_PATH.exists():
        cached = json.loads(TOKEN_PATH.read_text())
        expires = datetime.fromisoformat(cached["expires_at"])
        if datetime.now() < expires - timedelta(minutes=10):
            return cached["access_token"]

    res = requests.post(f"{BASE_URL}/oauth2/tokenP", json={
        "grant_type": "client_credentials",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET,
    })
    data = res.json()
    if "access_token" not in data:
        raise RuntimeError(f"토큰 발급 실패: {data}")

    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(json.dumps({
        "access_token": data["access_token"],
        "expires_at": (datetime.now() + timedelta(hours=23)).isoformat(),
    }))
    return data["access_token"]


def _headers(tr_id):
    return {
        "authorization": f"Bearer {_get_token()}",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET,
        "tr_id": tr_id,
        "Content-Type": "application/json; charset=utf-8",
    }


def _get(path, tr_id, params):
    """API GET 호출. 1초 대기 포함."""
    res = requests.get(f"{BASE_URL}{path}", headers=_headers(tr_id), params=params)
    time.sleep(0.5)  # rate limit 방어
    data = res.json()
    if data.get("rt_cd") != "0":
        print(f"  [WARN] {tr_id}: {data.get('msg1', 'unknown error')}")
        return None
    return data


# --- 개별 수집 함수 ---

def fetch_market_index():
    """KOSPI / KOSDAQ 지수"""
    result = {}
    for code, name in [("0001", "KOSPI"), ("1001", "KOSDAQ")]:
        data = _get(
            "/uapi/domestic-stock/v1/quotations/inquire-index-price",
            "FHPUP02100000",
            {"FID_COND_MRKT_DIV_CODE": "U", "FID_INPUT_ISCD": code},
        )
        if data:
            o = data["output"]
            result[name] = {
                "index": o.get("bstp_nmix_prpr", ""),
                "change": o.get("bstp_nmix_prdy_vrss", ""),
                "change_rate": o.get("bstp_nmix_prdy_ctrt", ""),
            }
    return result


def fetch_portfolio():
    """내 보유종목"""
    acct_prefix, acct_suffix = ACCOUNT.split("-")
    data = _get(
        "/uapi/domestic-stock/v1/trading/inquire-balance",
        "TTTC8434R",
        {
            "CANO": acct_prefix,
            "ACNT_PRDT_CD": acct_suffix,
            "AFHR_FLPR_YN": "N",
            "OFL_YN": "",
            "INQR_DVSN": "02",
            "UNPR_DVSN": "01",
            "FUND_STTL_ICLD_YN": "N",
            "FNCG_AMT_AUTO_RDPT_YN": "N",
            "PRCS_DVSN": "01",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": "",
        },
    )
    if not data:
        return {"stocks": [], "summary": {}}

    stocks = []
    for s in data.get("output1", []):
        stocks.append({
            "code": s.get("pdno", ""),
            "name": s.get("prdt_name", ""),
            "qty": int(s.get("hldg_qty", 0)),
            "avg_price": float(s.get("pchs_avg_pric", 0)),
            "cur_price": int(s.get("prpr", 0)),
            "pnl_rate": float(s.get("evlu_pfls_rt", 0)),
            "pnl_amt": int(s.get("evlu_pfls_amt", 0)),
            "eval_amt": int(s.get("evlu_amt", 0)),
        })

    summary = {}
    if data.get("output2"):
        s = data["output2"][0]
        summary = {
            "total_eval": int(s.get("tot_evlu_amt", 0)),
            "total_pnl": int(s.get("evlu_pfls_smtl_amt", 0)),
            "total_purchase": int(s.get("pchs_amt_smtl_amt", 0)),
        }
    return {"stocks": stocks, "summary": summary}


def fetch_trades():
    """오늘 매매내역"""
    acct_prefix, acct_suffix = ACCOUNT.split("-")
    today = datetime.now().strftime("%Y%m%d")
    data = _get(
        "/uapi/domestic-stock/v1/trading/inquire-daily-ccld",
        "TTTC8001R",
        {
            "CANO": acct_prefix,
            "ACNT_PRDT_CD": acct_suffix,
            "INQR_STRT_DT": today,
            "INQR_END_DT": today,
            "SLL_BUY_DVSN_CD": "00",
            "INQR_DVSN": "00",
            "PDNO": "",
            "CCLD_DVSN": "01",
            "ORD_GNO_BRNO": "",
            "ODNO": "",
            "INQR_DVSN_3": "00",
            "INQR_DVSN_1": "",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": "",
        },
    )
    if not data:
        return []

    trades = []
    for t in data.get("output1", []):
        trades.append({
            "name": t.get("prdt_name", ""),
            "side": t.get("sll_buy_dvsn_cd_name", ""),
            "qty": t.get("tot_ccld_qty", ""),
            "price": t.get("avg_prvs", t.get("ccld_avg_prvs", "")),
        })
    return trades


def fetch_top_gainers():
    """급등 TOP 10"""
    data = _get(
        "/uapi/domestic-stock/v1/ranking/fluctuation",
        "FHPST01700000",
        {
            "fid_rsfl_rate2": "30",
            "fid_cond_mrkt_div_code": "J",
            "fid_cond_scr_div_code": "20170",
            "fid_input_iscd": "0000",
            "fid_rank_sort_cls_code": "0",
            "fid_input_cnt_1": "10",
            "fid_prc_cls_code": "0",
            "fid_input_price_1": "0",
            "fid_input_price_2": "1000000",
            "fid_vol_cnt": "100000",
            "fid_trgt_cls_code": "0",
            "fid_trgt_exls_cls_code": "0",
            "fid_div_cls_code": "0",
            "fid_rsfl_rate1": "0",
        },
    )
    if not data:
        return []

    return [
        {
            "name": i.get("hts_kor_isnm", ""),
            "code": i.get("mksc_shrn_iscd", ""),
            "price": int(i.get("stck_prpr", 0)),
            "change_rate": i.get("prdy_ctrt", ""),
            "volume": int(i.get("acml_vol", 0)),
        }
        for i in data.get("output", [])[:10]
    ]


def fetch_top_volume():
    """거래량 TOP 10"""
    data = _get(
        "/uapi/domestic-stock/v1/quotations/volume-rank",
        "FHPST01710000",
        {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_COND_SCR_DIV_CODE": "20171",
            "FID_INPUT_ISCD": "0000",
            "FID_DIV_CLS_CODE": "0",
            "FID_BLNG_CLS_CODE": "0",
            "FID_TRGT_CLS_CODE": "111111111",
            "FID_TRGT_EXLS_CLS_CODE": "0000000000",
            "FID_INPUT_PRICE_1": "0",
            "FID_INPUT_PRICE_2": "1000000",
            "FID_VOL_CNT": "100000",
            "FID_INPUT_DATE_1": "",
        },
    )
    if not data:
        return []

    return [
        {
            "name": i.get("hts_kor_isnm", ""),
            "code": i.get("mksc_shrn_iscd", ""),
            "price": int(i.get("stck_prpr", 0)),
            "change_rate": i.get("prdy_ctrt", ""),
            "volume": int(i.get("acml_vol", 0)),
        }
        for i in data.get("output", [])[:10]
    ]


def fetch_watchlist():
    """관심종목 개별 시세 조회"""
    config = json.loads(CONFIG_PATH.read_text())
    watchlist = config.get("watchlist", [])
    if not watchlist:
        return []

    results = []
    for item in watchlist:
        code = item["code"]
        # ETF는 코드가 6자리가 아닐 수 있음
        mrkt = "J"
        data = _get(
            "/uapi/domestic-stock/v1/quotations/inquire-price",
            "FHKST01010100",
            {"FID_COND_MRKT_DIV_CODE": mrkt, "FID_INPUT_ISCD": code},
        )
        if data:
            o = data["output"]
            results.append({
                "code": code,
                "name": item["name"],
                "price": int(o.get("stck_prpr", 0)),
                "change": int(o.get("prdy_vrss", 0)),
                "change_rate": o.get("prdy_ctrt", "0"),
                "volume": int(o.get("acml_vol", 0)),
                "high": int(o.get("stck_hgpr", 0)),
                "low": int(o.get("stck_lwpr", 0)),
            })
    return results


def fetch_watchlist_us():
    """미국 관심종목 시세 조회"""
    config = json.loads(CONFIG_PATH.read_text())
    watchlist = config.get("watchlist_us", [])
    if not watchlist:
        return []

    results = []
    for item in watchlist:
        data = _get(
            "/uapi/overseas-price/v1/quotations/price",
            "HHDFS00000300",
            {"AUTH": "", "EXCD": item["excd"], "SYMB": item["code"]},
        )
        if data and data.get("output"):
            o = data["output"]
            results.append({
                "code": item["code"],
                "name": item["name"],
                "excd": item["excd"],
                "price": float(o.get("last", 0)),
                "change": float(o.get("diff", 0)),
                "change_rate": o.get("rate", "0"),
                "volume": int(o.get("tvol", 0)),
                "high": float(o.get("high", 0)),
                "low": float(o.get("low", 0)),
                "open": float(o.get("open", 0)),
            })
    return results


def fetch_us_balance():
    """미국주식 보유잔고 조회"""
    acct_prefix, acct_suffix = ACCOUNT.split("-")
    data = _get(
        "/uapi/overseas-stock/v1/trading/inquire-balance",
        "TTTS3012R",
        {
            "CANO": acct_prefix,
            "ACNT_PRDT_CD": acct_suffix,
            "OVRS_EXCG_CD": "NASD",
            "TR_CRCY_CD": "USD",
            "CTX_AREA_FK200": "",
            "CTX_AREA_NK200": "",
        },
    )
    if not data:
        return {"stocks": [], "summary": {}}

    stocks = []
    for s in data.get("output1", []):
        qty = int(s.get("ovrs_cblc_qty", 0))
        if qty == 0:
            continue
        stocks.append({
            "code": s.get("ovrs_pdno", ""),
            "name": s.get("ovrs_item_name", ""),
            "qty": qty,
            "avg_price": float(s.get("pchs_avg_pric", 0)),
            "cur_price": float(s.get("now_pric2", 0)),
            "pnl_rate": float(s.get("evlu_pfls_rt", 0)),
            "pnl_amt": float(s.get("frcr_evlu_pfls_amt", 0)),
            "eval_amt": float(s.get("ovrs_stck_evlu_amt", 0)),
        })

    summary = {}
    if data.get("output2"):
        s = data["output2"]
        if isinstance(s, list):
            s = s[0]
        summary = {
            "total_eval": float(s.get("tot_evlu_pfls_amt", 0)),
            "total_pnl": float(s.get("ovrs_tot_pfls", 0)),
        }
    return {"stocks": stocks, "summary": summary}


def fetch_foreign_institution():
    """외인/기관 순매수 TOP 10"""
    data = _get(
        "/uapi/domestic-stock/v1/quotations/foreign-institution-total",
        "FHPTJ04400000",
        {
            "FID_COND_MRKT_DIV_CODE": "V",
            "FID_COND_SCR_DIV_CODE": "16449",
            "FID_INPUT_ISCD": "0000",
            "FID_DIV_CLS_CODE": "0",
            "FID_RANK_SORT_CLS_CODE": "0",
            "FID_ETC_CLS_CODE": "0",
        },
    )
    if not data:
        return []

    return [
        {
            "name": i.get("hts_kor_isnm", ""),
            "code": i.get("mksc_shrn_iscd", ""),
            "foreign_net": int(i.get("frgn_ntby_qty", 0)),
            "institution_net": int(i.get("orgn_ntby_qty", 0)),
        }
        for i in data.get("output", [])[:10]
    ]


# --- 메인 ---

def main():
    print(f"[{datetime.now():%Y-%m-%d %H:%M}] 주식 데이터 수집 시작")

    report = {
        "source": "한국투자증권 OpenAPI",
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "market": fetch_market_index(),
        "portfolio": fetch_portfolio(),
        "trades": fetch_trades(),
        "watchlist": fetch_watchlist(),
        "top_gainers": fetch_top_gainers(),
        "top_volume": fetch_top_volume(),
        "foreign_institution": fetch_foreign_institution(),
        "watchlist_us": fetch_watchlist_us(),
        "portfolio_us": fetch_us_balance(),
    }

    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"  → {DATA_PATH} 저장 완료")

    # 요약 — 국내
    m = report["market"]
    for name, info in m.items():
        print(f"  {name}: {info['index']} ({info['change_rate']}%)")
    p = report["portfolio"]
    print(f"  [국내] 보유종목: {len(p['stocks'])}개")
    if p.get("summary"):
        print(f"  [국내] 총 평가: {p['summary'].get('total_eval', 0):,}원")
    print(f"  [국내] 관심종목: {len(report['watchlist'])}개")
    for w in report["watchlist"]:
        print(f"    {w['name']}: {w['price']:,}원 ({w['change_rate']}%)")

    # 요약 — 미국
    pu = report["portfolio_us"]
    print(f"  [미국] 보유종목: {len(pu['stocks'])}개")
    if pu.get("summary") and pu["summary"].get("total_eval"):
        print(f"  [미국] 총 평가손익: ${pu['summary'].get('total_pnl', 0):,.2f}")
    print(f"  [미국] 관심종목: {len(report['watchlist_us'])}개")
    for w in report["watchlist_us"]:
        print(f"    {w['name']}: ${w['price']:,.2f} ({w['change_rate']}%)")

    print(f"  급등 TOP: {len(report['top_gainers'])}개")
    print(f"  거래량 TOP: {len(report['top_volume'])}개")
    print(f"  외인/기관: {len(report['foreign_institution'])}개")
    print(f"  오늘 매매: {len(report['trades'])}건")


def deploy_to_vercel():
    """stock.json을 stock-report 레포에 push → Vercel 자동 배포"""
    if not REPORT_REPO.exists():
        subprocess.run(
            ["git", "clone", "https://github.com/thissak/stock-report.git", str(REPORT_REPO)],
            capture_output=True,
        )

    # stock.json 복사
    shutil.copy2(DATA_PATH, REPORT_REPO / "stock.json")

    # git push
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    cmds = [
        ["git", "-C", str(REPORT_REPO), "add", "stock.json"],
        ["git", "-C", str(REPORT_REPO), "commit", "-m", f"update: {today}"],
        ["git", "-C", str(REPORT_REPO), "push"],
    ]
    for cmd in cmds:
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0 and "nothing to commit" not in r.stdout + r.stderr:
            print(f"  [WARN] git: {r.stderr.strip()}")
            return False

    print("  → Vercel 배포 push 완료")
    return True


if __name__ == "__main__":
    main()
    deploy_to_vercel()

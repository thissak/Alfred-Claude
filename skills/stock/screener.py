#!/usr/bin/env python3
"""주식 스크리너 — 한투 종목 마스터 파일 기반 종목 필터링.

한투 OpenAPI 마스터 파일(kospi_code.mst, kosdaq_code.mst)을 다운로드하여
시가총액/수익성 등 복합 조건으로 전체 종목 스크리닝.
"""

import json
import os
import re
import ssl
import sys
import time
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_PATH = ROOT / "data"
CACHE_DIR = ROOT / "run" / "master"

sys.path.insert(0, str(ROOT / "src"))
from kis_readonly_client import get as kis_get


def _download_master(market):
    """종목 마스터 파일 다운로드 (kospi/kosdaq)."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    url = f"https://new.real.download.dws.co.kr/common/master/{market}_code.mst.zip"
    zip_path = CACHE_DIR / f"{market}_code.zip"

    ssl._create_default_https_context = ssl._create_unverified_context
    urllib.request.urlretrieve(url, str(zip_path))

    with zipfile.ZipFile(str(zip_path)) as z:
        z.extractall(str(CACHE_DIR))
    zip_path.unlink()

    return CACHE_DIR / f"{market}_code.mst"


def _parse_master(mst_path, part2_len=228):
    """마스터 파일 바이너리 파싱 → 종목 리스트.

    코스피: part2_len=228, 코스닥: part2_len=222
    """
    stocks = []
    with open(mst_path, "rb") as f:
        for line in f:
            line = line.rstrip(b"\n\r")
            if len(line) < part2_len + 10:
                continue

            # Part 1: 가변 길이 (단축코드 9 + 표준코드 12 + 한글명)
            part1 = line[: len(line) - part2_len]
            part2 = line[-part2_len:]

            code = part1[:9].decode("ascii", errors="replace").strip()
            name = part1[21:].decode("euc-kr", errors="replace").strip()

            # Part 2: 고정 너비 바이너리
            text = part2.decode("ascii", errors="replace")

            # 주요 필드 추출 (삼성전자로 검증된 오프셋)
            etp = text[12:13].strip()
            spac = text[19:20].strip()
            base_price = text[44:53].strip()      # 기준가 (9자리, 원 단위 *1000 포함)
            trading_halt = text[63:64].strip()     # 거래정지
            admin = text[65:66].strip()            # 관리종목
            volume = text[81:93].strip()           # 전일거래량

            # 뒤에서부터 역산 (삼성전자 실데이터로 검증)
            # [-3:]   = NNN (대주/담보/신용 1+1+1)
            # [-6:-3] = 그룹사코드 (3)
            # [-15:-6] = 시가총액 (9, 억원)
            # [-23:-15] = 기준년월 (8, YYYYMMDD)
            # [-32:-23] = ROE (9)
            # [-37:-32] = 당기순이익 (5, 억원)
            # [-46:-37] = 경상이익 (9, 억원)
            # [-55:-46] = 영업이익 (9, 억원)
            # [-64:-55] = 매출액 (9, 억원)
            mktcap_str = text[-15:-6].strip()
            fiscal_ym = text[-23:-15].strip()
            roe_str = text[-32:-23].strip()
            net_profit_str = text[-37:-32].strip()
            ordinary_profit_str = text[-46:-37].strip()
            oper_profit_str = text[-55:-46].strip()
            revenue_str = text[-64:-55].strip()

            def safe_int(s):
                try:
                    return int(s)
                except (ValueError, TypeError):
                    return 0

            def safe_float(s):
                try:
                    return float(s)
                except (ValueError, TypeError):
                    return 0.0

            stocks.append({
                "code": code,
                "name": name,
                "price": safe_int(base_price) // 1000 if len(base_price) > 3 else safe_int(base_price),
                "etp": etp,
                "spac": spac,
                "trading_halt": trading_halt,
                "admin": admin,
                "volume": safe_int(volume),
                "mktcap": safe_int(mktcap_str),         # 억원
                "revenue": safe_int(revenue_str),         # 억원
                "oper_profit": safe_int(oper_profit_str), # 억원
                "net_profit": safe_int(net_profit_str),   # 억원 (5자리라 제한적)
                "roe": safe_float(roe_str),
                "fiscal_ym": fiscal_ym,
            })

    return stocks


def fetch_income_years(code, years=4):
    """종목의 연도별 영업이익 조회 (KIS 손익계산서 API).

    Returns: list of (year, oper_profit) or None on failure.
    """
    data = kis_get(
        "/uapi/domestic-stock/v1/finance/income-statement",
        "FHKST66430200",
        {
            "FID_DIV_CLS_CODE": "0",  # 0=년
            "fid_cond_mrkt_div_code": "J",
            "fid_input_iscd": code,
        },
    )
    if not data:
        return None

    results = []
    for item in data.get("output", []):
        year = item.get("stac_yymm", "")
        oper_str = item.get("bsop_prti", "0")
        try:
            results.append((year, int(float(oper_str))))
        except (ValueError, TypeError):
            continue
    return results


def check_consecutive_profit(code, min_years=4):
    """N년 연속 영업이익 흑자 확인.

    Returns: (bool, list of (year, profit))
    """
    years_data = fetch_income_years(code)
    if not years_data or len(years_data) < min_years:
        return False, years_data or []

    # 최근 N년 확인
    recent = years_data[:min_years]
    all_profitable = all(profit > 0 for _, profit in recent)
    return all_profitable, recent


def screen(stocks, market_name, cap_limit=1000):
    """시가총액 cap_limit억 미만 + 흑자 필터링."""
    spac_re = re.compile(r"스팩|SPAC", re.IGNORECASE)
    filtered = [
        s for s in stocks
        if s["etp"] != "Y"
        and s["spac"] != "Y"
        and s["admin"] not in ("Y", "1")
        and s["trading_halt"] not in ("Y", "1")
        and not spac_re.search(s["name"])
    ]

    # 시가총액 필터
    small = [s for s in filtered if 0 < s["mktcap"] < cap_limit]

    # 흑자 필터 (영업이익 > 0)
    profitable = [s for s in small if s["oper_profit"] > 0]

    # 시가총액 오름차순
    profitable.sort(key=lambda x: x["mktcap"])

    print(f"[{market_name}] 전체 {len(stocks)} → 필터 후 {len(filtered)} → 시총<{cap_limit}억 {len(small)} → 흑자 {len(profitable)}")
    return profitable


def main():
    print(f"[{datetime.now():%Y-%m-%d %H:%M}] 주식 스크리닝 시작")
    print("마스터 파일 다운로드 중...")

    # 코스피
    mst = _download_master("kospi")
    kospi_stocks = _parse_master(mst, part2_len=228)
    kospi_result = screen(kospi_stocks, "코스피")

    # 코스닥
    mst = _download_master("kosdaq")
    kosdaq_stocks = _parse_master(mst, part2_len=222)
    kosdaq_result = screen(kosdaq_stocks, "코스닥")

    # 검증: 삼성전자 데이터 확인
    samsung = [s for s in kospi_stocks if s["name"] == "삼성전자"]
    if samsung:
        s = samsung[0]
        print(f"\n[검증] 삼성전자: 시총={s['mktcap']:,}억, 영업이익={s['oper_profit']:,}억, ROE={s['roe']}")

    # 2단계: 4년 연속 흑자 필터 (KIS 손익계산서 API)
    all_candidates = [("코스피", kospi_result), ("코스닥", kosdaq_result)]
    final_results = {}

    for market_name, candidates in all_candidates:
        print(f"\n[{market_name}] {len(candidates)}종목 4년 연속 흑자 검증 중...")
        passed = []
        for i, s in enumerate(candidates):
            ok, years = check_consecutive_profit(s["code"], min_years=4)
            if ok:
                s["profit_years"] = [(y, p) for y, p in years]
                passed.append(s)
            if (i + 1) % 50 == 0:
                print(f"  {i+1}/{len(candidates)} 확인 완료 (통과: {len(passed)})")
        print(f"  → {market_name}: {len(passed)}종목 통과")
        final_results[market_name] = passed

    # 결과 저장
    output = {
        "screened_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "condition": "시가총액 1000억 미만 + 4년 연속 영업이익 흑자",
        "kospi": {"count": len(final_results["코스피"]), "stocks": final_results["코스피"]},
        "kosdaq": {"count": len(final_results["코스닥"]), "stocks": final_results["코스닥"]},
    }

    out_path = DATA_PATH / "screener.json"
    DATA_PATH.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"\n결과 저장: {out_path}")

    # 요약 출력
    print(f"\n{'='*80}")
    print(f"스크리닝 결과: 시가총액 1000억 미만 + 4년 연속 영업이익 흑자")
    print(f"{'='*80}")

    for name in ["코스피", "코스닥"]:
        stocks = final_results[name]
        print(f"\n[{name}] {len(stocks)}종목")
        if stocks:
            print(f"{'종목명':>14} {'코드':>8} {'시총(억)':>8} {'영업이익':>10} {'ROE':>8} {'4년 영업이익 추이':>30}")
            print("-" * 85)
            for s in stocks[:40]:
                trend = " → ".join(f"{p:,}" for _, p in s.get("profit_years", []))
                print(
                    f"{s['name']:>14} {s['code']:>8} "
                    f"{s['mktcap']:>8,} {s['oper_profit']:>10,} "
                    f"{s['roe']:>8.1f}  {trend}"
                )
            if len(stocks) > 40:
                print(f"  ... 외 {len(stocks) - 40}종목")


if __name__ == "__main__":
    main()

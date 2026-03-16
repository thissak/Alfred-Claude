#!/usr/bin/env python3
"""주식 모니터 — 스크리닝된 종목의 일일 가격/거래량 변동 추적.

매일 장 마감 후 실행. 마스터 파일 기반이라 API 호출 없음.
전일 대비 특이사항(급등/급락, 거래량 폭증 등) 감지.
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from screener import _download_master, _parse_master

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "research"))
from save_note import md_to_html, _save_to_notes

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "data"
MONITOR_DIR = DATA_DIR / "monitor"
WATCHLIST_PATH = DATA_DIR / "monitor-watchlist.json"
SCREENER_PATH = DATA_DIR / "screener.json"

# 특이사항 기준
VOLUME_SPIKE_RATIO = 3.0   # 전일 대비 거래량 N배 이상
PRICE_CHANGE_PCT = 5.0     # 전일 대비 등락률 N% 이상
PRICE_SURGE_PCT = 10.0     # 급등 기준


def load_watchlist():
    """모니터링 대상 종목 로드. 없으면 screener.json에서 생성."""
    if WATCHLIST_PATH.exists():
        return json.loads(WATCHLIST_PATH.read_text())

    # screener.json에서 초기 생성
    if not SCREENER_PATH.exists():
        print("[monitor] screener.json 없음. 먼저 screener.py 실행 필요")
        return {"stocks": {}}

    screener = json.loads(SCREENER_PATH.read_text())
    watchlist = {"created_at": screener["screened_at"], "condition": screener["condition"], "stocks": {}}

    for market in ["kospi", "kosdaq"]:
        for s in screener[market]["stocks"]:
            code = s["code"]
            watchlist["stocks"][code] = {
                "name": s["name"],
                "market": market,
                "mktcap": s["mktcap"],
                "oper_profit": s["oper_profit"],
                "roe": s["roe"],
                "profit_years": s.get("profit_years", []),
            }

    WATCHLIST_PATH.write_text(json.dumps(watchlist, ensure_ascii=False, indent=2))
    print(f"[monitor] 워치리스트 생성: {len(watchlist['stocks'])}종목")
    return watchlist


def load_prev_snapshot():
    """전일 스냅샷 로드."""
    snapshots = sorted(MONITOR_DIR.glob("*.json"), reverse=True)
    if not snapshots:
        return None
    return json.loads(snapshots[0].read_text())


def take_snapshot(watchlist):
    """오늘자 마스터 파일에서 모니터링 종목 데이터 추출."""
    watch_codes = set(watchlist["stocks"].keys())
    today_data = {}

    for market, part2_len in [("kospi", 228), ("kosdaq", 222)]:
        mst = _download_master(market)
        stocks = _parse_master(mst, part2_len)
        for s in stocks:
            if s["code"] in watch_codes:
                today_data[s["code"]] = {
                    "name": s["name"],
                    "price": s["price"],
                    "volume": s["volume"],
                    "mktcap": s["mktcap"],
                    "oper_profit": s["oper_profit"],
                }

    return today_data


def detect_alerts(today, prev, watchlist):
    """전일 대비 특이사항 감지."""
    alerts = []

    for code, cur in today.items():
        meta = watchlist["stocks"].get(code, {})
        name = cur["name"]

        if prev and code in prev:
            old = prev[code]
            old_price = old.get("price", 0)
            old_vol = old.get("volume", 0)

            # 가격 변동률
            if old_price > 0:
                pct = (cur["price"] - old_price) / old_price * 100
            else:
                pct = 0

            # 거래량 변동 배수
            if old_vol > 0:
                vol_ratio = cur["volume"] / old_vol
            else:
                vol_ratio = 0

            # 급등/급락
            if abs(pct) >= PRICE_SURGE_PCT:
                direction = "급등" if pct > 0 else "급락"
                alerts.append({
                    "type": direction,
                    "code": code,
                    "name": name,
                    "detail": f"{pct:+.1f}% ({old_price:,}→{cur['price']:,})",
                    "volume": cur["volume"],
                    "severity": "high",
                })
            elif abs(pct) >= PRICE_CHANGE_PCT:
                direction = "상승" if pct > 0 else "하락"
                alerts.append({
                    "type": f"가격 {direction}",
                    "code": code,
                    "name": name,
                    "detail": f"{pct:+.1f}% ({old_price:,}→{cur['price']:,})",
                    "volume": cur["volume"],
                    "severity": "medium",
                })

            # 거래량 폭증
            if vol_ratio >= VOLUME_SPIKE_RATIO and cur["volume"] > 10000:
                alerts.append({
                    "type": "거래량 폭증",
                    "code": code,
                    "name": name,
                    "detail": f"{vol_ratio:.1f}배 ({old_vol:,}→{cur['volume']:,})",
                    "price_change": f"{pct:+.1f}%",
                    "severity": "high" if vol_ratio >= 5 else "medium",
                })

    # severity 순 정렬
    severity_order = {"high": 0, "medium": 1, "low": 2}
    alerts.sort(key=lambda x: severity_order.get(x["severity"], 9))
    return alerts


def format_report(alerts, today, prev, date_str):
    """보고서 생성."""
    lines = [f"# 모니터링 리포트 ({date_str})", ""]

    if not alerts:
        lines.append("특이사항 없음.")
        return "\n".join(lines)

    lines.append(f"## 특이사항 {len(alerts)}건")
    lines.append("")

    for a in alerts:
        icon = {"high": "[!]", "medium": "[*]", "low": "[-]"}.get(a["severity"], "[-]")
        lines.append(f"{icon} **{a['name']}** ({a['code']}) — {a['type']}: {a['detail']}")

    # 통계
    lines.append("")
    lines.append("## 통계")
    if prev:
        up = sum(1 for c in today if c in prev and today[c]["price"] > prev[c].get("price", 0))
        down = sum(1 for c in today if c in prev and today[c]["price"] < prev[c].get("price", 0))
        flat = len(today) - up - down
        lines.append(f"- 상승: {up}종목 / 하락: {down}종목 / 보합: {flat}종목")

    return "\n".join(lines)


def main():
    today_str = datetime.now().strftime("%Y-%m-%d")
    print(f"[{today_str}] 주식 모니터링 시작")

    # 1. 워치리스트 로드
    watchlist = load_watchlist()
    if not watchlist["stocks"]:
        print("[monitor] 모니터링 대상 없음")
        return

    print(f"모니터링 대상: {len(watchlist['stocks'])}종목")

    # 2. 전일 스냅샷 로드
    prev = load_prev_snapshot()
    if prev:
        print(f"전일 데이터: {prev.get('date', 'unknown')} ({len(prev.get('stocks', {}))}종목)")
    else:
        print("전일 데이터 없음 (첫 실행)")

    # 3. 오늘 스냅샷 생성
    print("마스터 파일 다운로드 중...")
    today_data = take_snapshot(watchlist)
    print(f"오늘 데이터: {len(today_data)}종목 수집")

    # 4. 특이사항 감지
    prev_stocks = prev.get("stocks", {}) if prev else {}
    alerts = detect_alerts(today_data, prev_stocks, watchlist)

    # 5. 리포트 생성
    report = format_report(alerts, today_data, prev_stocks, today_str)
    print(f"\n{report}")

    # 6. 스냅샷 저장
    MONITOR_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = {
        "date": today_str,
        "stock_count": len(today_data),
        "alert_count": len(alerts),
        "stocks": today_data,
        "alerts": alerts,
    }
    snapshot_path = MONITOR_DIR / f"{today_str}.json"
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2))
    print(f"\n스냅샷 저장: {snapshot_path}")

    # 7. 리포트 저장
    report_path = MONITOR_DIR / f"{today_str}.md"
    report_path.write_text(report)
    print(f"리포트 저장: {report_path}")

    # 8. Apple Notes 공유 폴더에 발송
    if alerts:
        try:
            html = md_to_html(report)
            title = f"주식 모니터링 {today_str} ({len(alerts)}건)"
            if _save_to_notes(title, html):
                print(f"Apple Notes 발송 완료: {title}")
            else:
                print("Apple Notes 발송 실패")
        except Exception as e:
            print(f"Apple Notes 발송 에러: {e}")

    return alerts


if __name__ == "__main__":
    main()

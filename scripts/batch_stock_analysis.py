"""전 종목 배치 분석 — 유니버스 필터 + claude -p 병렬 실행."""

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import market_db as db


# ── 유니버스 필터 ─────────────────────────────────────────

def get_analysis_universe(date: str) -> list[dict]:
    """분석 대상 종목 추출. 노이즈 제거 후 시총 내림차순."""
    d = datetime.strptime(date, "%Y-%m-%d")
    d40 = (d - timedelta(days=40)).strftime("%Y-%m-%d")
    d365 = (d - timedelta(days=365)).strftime("%Y-%m-%d")

    return db._query(f"""
        WITH liquid AS (
            SELECT dp.code,
                   MAX(CASE WHEN dp.date = ? THEN dp.mktcap END) as mktcap,
                   AVG(dp.trade_value) as avg_tv,
                   AVG(dp.volume) as avg_vol
            FROM daily_prices dp
            WHERE dp.date BETWEEN ? AND ?
            GROUP BY dp.code
            HAVING mktcap >= 500
               AND avg_tv >= 500000000
               AND avg_vol >= 50000
        ),
        loss3 AS (
            SELECT code FROM (
                SELECT code, net_profit,
                       ROW_NUMBER() OVER (PARTITION BY code ORDER BY period DESC) as rn
                FROM financials
                WHERE period_type = 'annual' AND net_profit IS NOT NULL
            )
            WHERE rn <= 3
            GROUP BY code
            HAVING COUNT(*) = 3
               AND SUM(CASE WHEN net_profit < 0 THEN 1 ELSE 0 END) = 3
        )
        SELECT s.code, s.name, s.market, s.sector, l.mktcap
        FROM liquid l
        JOIN securities s ON s.code = l.code
        LEFT JOIN loss3 cl ON cl.code = l.code
        WHERE s.is_etp = 0 AND s.is_spac = 0
          AND s.is_halt = 0 AND s.is_admin = 0
          AND s.delisted_at IS NULL
          AND (s.listed_at IS NULL OR s.listed_at <= ?)
          AND (cl.code IS NULL
               OR s.sector IN ('제약', '의료·정밀기기'))
        ORDER BY l.mktcap DESC
    """, [date, d40, date, d365])


# ── 데이터 수집 ──────────────────────────────────────────

def _thread_query(sql, params=None):
    """스레드 안전한 쿼리 (스레드별 커넥션)."""
    import sqlite3 as _sqlite3
    conn = _sqlite3.connect(db.DB_PATH)
    conn.row_factory = _sqlite3.Row
    rows = [dict(r) for r in conn.execute(sql, params or []).fetchall()]
    conn.close()
    return rows


def collect_stock_data(code: str) -> dict:
    """market.db에서 종목 데이터 수집."""
    prices = _thread_query(
        "SELECT * FROM daily_prices WHERE code=? ORDER BY date DESC LIMIT 20", [code])
    flow = _thread_query(
        "SELECT * FROM investor_flow WHERE code=? ORDER BY date DESC", [code])
    financials = _thread_query(
        "SELECT period, period_type, revenue, oper_profit, net_profit, roe, eps, bps, "
        "debt_ratio, revenue_growth, oper_profit_growth, ev_ebitda "
        "FROM financials WHERE code=? ORDER BY period DESC LIMIT 4", [code])
    val = _thread_query(
        "SELECT per, pbr, eps, bps, foreign_ratio "
        "FROM daily_valuations WHERE code=? ORDER BY date DESC LIMIT 1", [code])
    return {
        "prices_20d": [
            {"date": p["date"], "close": p["close"], "change": p["change_rate"] or 0,
             "volume": p["volume"]}
            for p in (prices or [])[:20]
        ],
        "flow_10d": [
            {"date": f["date"], "foreign": f["foreign_net"],
             "inst": f["institution_net"]}
            for f in (flow or [])[:10]
        ],
        "financials": financials or [],
        "valuation": val[0] if val else {},
    }


def format_stock_data(stock: dict, data: dict) -> str:
    """종목 데이터를 텍스트로 포맷."""
    lines = [f"### {stock['code']} {stock['name']} | 섹터: {stock['sector'] or 'N/A'} | 시총: {stock['mktcap']:,}억"]

    # 밸류에이션
    v = data.get("valuation", {})
    if v:
        lines.append(f"밸류: PER={v.get('per','N/A')} PBR={v.get('pbr','N/A')} EPS={v.get('eps','N/A')} 외인비율={v.get('foreign_ratio','N/A')}%")

    # 최근 시세 (5일)
    prices = data.get("prices_20d", [])[:5]
    if prices:
        price_str = " | ".join(f"{p['date'][-5:]}: {p['close']:,}({p['change']:+.1f}%)" for p in prices)
        lines.append(f"시세(5일): {price_str}")

    # 20일 추이 요약
    if len(data.get("prices_20d", [])) >= 2:
        p20 = data["prices_20d"]
        ret_20d = (p20[0]["close"] / p20[-1]["close"] - 1) * 100 if p20[-1]["close"] else 0
        avg_vol = sum(p["volume"] for p in p20) / len(p20)
        lines.append(f"20일수익률: {ret_20d:+.1f}% | 평균거래량: {avg_vol:,.0f}")

    # 수급 (10일)
    flow = data.get("flow_10d", [])
    if flow:
        fgn_sum = sum(f["foreign"] for f in flow)
        inst_sum = sum(f["inst"] for f in flow)
        lines.append(f"10일수급: 외인={fgn_sum:+,.0f} 기관={inst_sum:+,.0f}")

    # 재무
    fins = data.get("financials", [])
    if fins:
        for f in fins[:2]:
            lines.append(
                f"  {f['period']}({f['period_type']}): 매출={f.get('revenue','N/A')} "
                f"영업이익={f.get('oper_profit','N/A')} 순이익={f.get('net_profit','N/A')} "
                f"ROE={f.get('roe','N/A')} 부채비율={f.get('debt_ratio','N/A')}"
            )

    return "\n".join(lines)


# ── 배치 실행 ─────────────────────────────────────────────

PROMPT_TEMPLATE = """너는 한국 주식 분석가다. 아래 종목 데이터를 보고 종합 판단해서 JSON 배열로만 출력해.

코드 실행 필요 없음. 아래 데이터만으로 판단해.

{stock_data}

위 데이터를 기반으로 각 종목의 JSON을 만들어.
반드시 JSON 배열만 출력. 앞뒤에 다른 텍스트, 마크다운 코드블록 없이 순수 JSON만.

[{{"code":"종목코드","name":"종목명","signal":"buy|watch|sell","score":0~100,"summary":"한줄요약","reason":"판단근거2-3줄","strengths":["강점1","강점2"],"risks":["리스크1","리스크2"]}}]

signal: buy=매수매력높음, watch=관망, sell=회피/매도
score: 밸류에이션(25)+수급(25)+재무(25)+모멘텀(25)=100
"""


def run_batch(batch: list[dict], batch_id: int, timeout: int = 300) -> list[dict]:
    """데이터 수집 후 claude -p로 배치 분석 실행."""
    # 데이터 수집
    stock_blocks = []
    for s in batch:
        data = collect_stock_data(s["code"])
        stock_blocks.append(format_stock_data(s, data))

    stock_data = "\n\n".join(stock_blocks)
    prompt = PROMPT_TEMPLATE.format(stock_data=stock_data)

    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--max-turns", "3"],
            capture_output=True, text=True, timeout=timeout,
            cwd=os.path.expanduser("~/Projects/Alfred-Claude"),
        )
        output = result.stdout.strip()
        if not output:
            print(f"  [WARN] Batch {batch_id}: stdout 비어있음", file=sys.stderr)
            return []

        # JSON 배열 추출 (앞뒤 텍스트/코드블록 무시)
        start = output.find("[")
        end = output.rfind("]")
        if start >= 0 and end > start:
            json_str = output[start:end + 1]
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                # 잘린 JSON 복구 시도: 마지막 완전한 } 까지만 파싱
                last_brace = json_str.rfind("}")
                if last_brace > 0:
                    return json.loads(json_str[:last_brace + 1] + "]")
                raise
        else:
            print(f"  [WARN] Batch {batch_id}: JSON 미발견. output[-200:]={output[-200:]}", file=sys.stderr)
            return []
    except subprocess.TimeoutExpired:
        print(f"  [WARN] Batch {batch_id}: 타임아웃 ({timeout}s)", file=sys.stderr)
        return []
    except json.JSONDecodeError as e:
        print(f"  [WARN] Batch {batch_id}: JSON 파싱 실패 - {e}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"  [ERROR] Batch {batch_id}: {e}", file=sys.stderr)
        return []


def main():
    parser = argparse.ArgumentParser(description="전 종목 배치 분석")
    parser.add_argument("--date", default=db.get_latest_date())
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()

    date = args.date
    print(f"=== 전 종목 배치 분석 ({date}) ===\n")

    # 1. 유니버스
    t0 = time.time()
    universe = get_analysis_universe(date)
    print(f"유니버스: {len(universe)}종목 ({time.time() - t0:.1f}s)")

    if args.limit > 0:
        universe = universe[:args.limit]
        print(f"  → 테스트 모드: 상위 {args.limit}종목만")

    # 2. 배치 분할
    batches = []
    for i in range(0, len(universe), args.batch_size):
        batches.append(universe[i:i + args.batch_size])
    print(f"배치: {len(batches)}개 (각 {args.batch_size}종목, workers={args.workers})")
    print()

    # 3. 병렬 실행
    all_results = []
    t1 = time.time()

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(run_batch, batch, i, args.timeout): i
            for i, batch in enumerate(batches)
        }
        for future in as_completed(futures):
            batch_id = futures[future]
            results = future.result()
            all_results.extend(results)
            print(f"  Batch {batch_id}/{len(batches)-1} 완료: {len(results)}종목")

    elapsed = time.time() - t1
    print(f"\n분석 완료: {len(all_results)}/{len(universe)}종목 ({elapsed:.0f}s)")

    # 4. 정렬 + 저장
    all_results.sort(key=lambda x: x.get("score", 0), reverse=True)

    out_dir = Path(__file__).resolve().parent.parent / "data" / "batch-analysis"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{date}_universe.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"저장: {out_file}")

    # 5. TOP 30 출력
    print(f"\n{'='*80}")
    print(f" TOP 30 종목 ({date})")
    print(f"{'='*80}")
    print(f"{'#':>3} {'코드':>8} {'종목명':<14} {'신호':>4} {'점수':>4} {'요약'}")
    print(f"{'-'*80}")
    for i, r in enumerate(all_results[:30], 1):
        signal_map = {"buy": "매수", "watch": "관망", "sell": "매도"}
        sig = signal_map.get(r.get("signal", ""), r.get("signal", ""))
        print(f"{i:3d} {r['code']:>8} {r.get('name',''):<14} {sig:>4} {r.get('score',0):4d} {r.get('summary','')}")

    # 6. 신호 분포
    from collections import Counter
    dist = Counter(r.get("signal", "unknown") for r in all_results)
    print(f"\n신호 분포: {dict(dist)}")


if __name__ == "__main__":
    main()

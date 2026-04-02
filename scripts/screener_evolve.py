"""정배열 스크리너 진화 루프 — 백데이터 기반 G/D 사이클."""

import argparse
import json
import os
import random
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import market_db as db

PROJECT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = PROJECT / "prompts"
RESULTS_DIR = PROJECT / "data" / "screener-evolve"


def get_trading_dates(start, end):
    """거래일 목록."""
    rows = db._query(
        "SELECT DISTINCT date FROM daily_prices WHERE date BETWEEN ? AND ? ORDER BY date",
        [start, end],
    )
    return [r["date"] for r in rows]


def compute_ma_status(code, as_of_date):
    """���정 날짜 기준 MA 정배열 상태 계산."""
    prices = db._query(
        "SELECT date, close FROM daily_prices WHERE code=? AND date<=? ORDER BY date DESC LIMIT 120",
        [code, as_of_date],
    )
    if len(prices) < 120:
        return None

    closes = [p["close"] for p in reversed(prices)]
    ma5 = sum(closes[-5:]) / 5
    ma20 = sum(closes[-20:]) / 20
    ma60 = sum(closes[-60:]) / 60
    ma120 = sum(closes[-120:]) / 120

    aligned = ma5 > ma20 > ma60 > ma120
    semi = ma5 > ma20 > ma60 and ma60 <= ma120

    return {
        "ma5": round(ma5), "ma20": round(ma20),
        "ma60": round(ma60), "ma120": round(ma120),
        "aligned": aligned, "semi_aligned": semi,
        "close": closes[-1],
    }


def collect_stock_snapshot(code, date):
    """특정 날짜 기준 종목 스냅샷."""
    ma = compute_ma_status(code, date)
    if not ma:
        return None

    prices = db._query(
        "SELECT date, close, volume, change_rate FROM daily_prices "
        "WHERE code=? AND date<=? ORDER BY date DESC LIMIT 20",
        [code, date],
    )
    flow = db._query(
        "SELECT date, foreign_net, institution_net FROM investor_flow "
        "WHERE code=? AND date<=? ORDER BY date DESC LIMIT 10",
        [code, date],
    )
    val = db._query(
        "SELECT per, pbr, foreign_ratio FROM daily_valuations "
        "WHERE code=? AND date<=? ORDER BY date DESC LIMIT 1",
        [code, date],
    )
    fins = db._query(
        "SELECT period, revenue, oper_profit, net_profit, roe "
        "FROM financials WHERE code=? AND period<=? ORDER BY period DESC LIMIT 2",
        [code, date],
    )

    return {
        "ma": ma,
        "prices_5d": [
            {"date": p["date"], "close": p["close"],
             "chg": p["change_rate"] or 0, "vol": p["volume"]}
            for p in prices[:5]
        ],
        "flow_10d_sum": {
            "foreign": sum(f["foreign_net"] or 0 for f in flow),
            "institution": sum(f["institution_net"] or 0 for f in flow),
        },
        "valuation": dict(val[0]) if val else {},
        "financials": [dict(f) for f in fins[:2]],
    }


def format_for_prompt(stock, snapshot):
    """프롬프트용 텍스트 포맷."""
    ma = snapshot["ma"]
    status = "정배열" if ma["aligned"] else ("준정배열" if ma["semi_aligned"] else "역배열")
    lines = [
        f"### {stock['code']} {stock['name']} | {stock.get('sector','N/A')} | 시총 {stock['mktcap']:,}억",
        f"MA: {status} | 5={ma['ma5']:,} 20={ma['ma20']:,} 60={ma['ma60']:,} 120={ma['ma120']:,} | 종가={ma['close']:,}",
    ]
    p5 = snapshot["prices_5d"]
    if p5:
        lines.append("5일시세: " + " | ".join(f"{p['date'][-5:]}:{p['close']:,}({p['chg']:+.1f}%)" for p in p5))
    fl = snapshot["flow_10d_sum"]
    lines.append(f"10일수급: 외인={fl['foreign']:+,.0f} 기관={fl['institution']:+,.0f}")
    v = snapshot["valuation"]
    if v:
        lines.append(f"밸류: PER={v.get('per','N/A')} PBR={v.get('pbr','N/A')}")
    for f in snapshot["financials"]:
        lines.append(f"  {f['period']}: 매출={f.get('revenue','N/A')} 영업={f.get('oper_profit','N/A')} ROE={f.get('roe','N/A')}")
    return "\n".join(lines)


def check_future(code, start_date, check_days=20):
    """start_date 이후 check_days 거래��� 동안 정배열 유지 여부."""
    dates = get_trading_dates(start_date, "2026-12-31")
    if len(dates) < check_days + 1:
        return None

    target_dates = dates[1:check_days + 1]
    alignment_days = 0
    last_close = None
    for d in target_dates:
        ma = compute_ma_status(code, d)
        if ma and ma["aligned"]:
            alignment_days += 1
        last_close = ma["close"] if ma else last_close

    first_close = None
    ma0 = compute_ma_status(code, start_date)
    if ma0:
        first_close = ma0["close"]

    return_pct = ((last_close / first_close) - 1) * 100 if first_close and last_close else None

    return {
        "check_days": check_days,
        "alignment_days": alignment_days,
        "alignment_ratio": round(alignment_days / check_days, 2),
        "return_pct": round(return_pct, 2) if return_pct else None,
        "maintained": alignment_days >= check_days * 0.8,
    }


# ── 유니버스 + 샘플링 ────────────────────────────────────

def get_universe(screen_date):
    """백테스트용 유니버스."""
    universe = db._query("""
        SELECT s.code, s.name, s.market, s.sector,
               dp.close * dp.volume / 100000000 as approx_mktcap_proxy
        FROM daily_prices dp
        JOIN securities s ON s.code = dp.code
        WHERE dp.date = ?
          AND s.is_etp = 0 AND s.is_spac = 0
          AND s.is_halt = 0 AND s.is_admin = 0
          AND dp.volume > 50000
        ORDER BY dp.close * dp.volume DESC
        LIMIT 500
    """, [screen_date])
    for u in universe:
        u["mktcap"] = int(u.get("approx_mktcap_proxy") or 0)
    return universe


def sample_and_snapshot(universe, screen_date, sample_size, seed=None):
    """시드 기반 샘플링 + 스냅샷 수집. 동일 시드 → 동일 샘플."""
    rng = random.Random(seed)
    sample = rng.sample(universe, min(sample_size, len(universe)))

    snapshots = {}
    for s in sample:
        snap = collect_stock_snapshot(s["code"], screen_date)
        if snap:
            snapshots[s["code"]] = {"stock": s, "snapshot": snap}
    return sample, snapshots


# ── Generator / Discriminator ─────────────────────────────

def _call_claude(prompt, system_prompt_file=None, timeout=120):
    """claude -p 호출. 도구 없이 1턴 즉시 응답."""
    cmd = ["claude", "-p", prompt, "--allowedTools", "", "--max-turns", "1", "--output-format", "text"]
    if system_prompt_file:
        cmd += ["--append-system-prompt-file", str(system_prompt_file)]
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout, cwd=str(PROJECT),
    )
    output = result.stdout.strip()
    if output.startswith("Error: Reached max turns"):
        return ""
    return output


def run_generator(stocks_data, prompt_version="v001"):
    """Generator 실행. JSON 배열 또는 {selected:[...]} 형식 지원."""
    prompt_file = PROMPTS_DIR / f"screener_{prompt_version}.md"
    prompt = "## 분석 대상\n\n" + stocks_data + "\n\nJSON만 출력. 다른 텍스트 없이."

    output = _call_claude(prompt, system_prompt_file=prompt_file)

    # 1차: JSON object { ... }
    obj_start = output.find("{")
    obj_end = output.rfind("}")
    if obj_start >= 0 and obj_end > obj_start:
        try:
            parsed = json.loads(output[obj_start:obj_end + 1])
            if isinstance(parsed, dict) and "selected" in parsed:
                return parsed["selected"]
            if isinstance(parsed, dict):
                return [parsed]
        except json.JSONDecodeError:
            pass

    # 2차: JSON array [ ... ]
    arr_start = output.find("[")
    arr_end = output.rfind("]")
    if arr_start >= 0 and arr_end > arr_start:
        try:
            return json.loads(output[arr_start:arr_end + 1])
        except json.JSONDecodeError:
            last_brace = output[:arr_end].rfind("}")
            if last_brace > arr_start:
                return json.loads(output[arr_start:last_brace + 1] + "]")

    print(f"  [WARN] Generator: JSON 파싱 실패", file=sys.stderr)
    return []


def run_discriminator(gen_results, actual_results, overlooked):
    """Discriminator 실행."""
    prompt_file = PROMPTS_DIR / "discriminator_v001.md"
    data = (
        f"## Generator 예측\n```json\n{json.dumps(gen_results, ensure_ascii=False, indent=2)}\n```\n\n"
        f"## 실제 결과\n```json\n{json.dumps(actual_results, ensure_ascii=False, indent=2)}\n```\n\n"
        f"## Generator가 선별하지 않았으나 정배열 유지한 종목\n```json\n{json.dumps(overlooked, ensure_ascii=False, indent=2)}\n```\n\n"
        f"JSON만 출력. 다른 텍스트 없이."
    )
    output = _call_claude(data, system_prompt_file=prompt_file)
    start = output.find("{")
    end = output.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(output[start:end + 1])
        except json.JSONDecodeError:
            pass
    return {}


# ── 프롬프트 진화 ─────────────────────────────────────────

def evolve_prompt(current_version, disc_result):
    """D 피드백 기반 다음 버전 프롬프트 자동 생성 (과교정 방지 가드레일 포함)."""
    current_file = PROMPTS_DIR / f"screener_{current_version}.md"
    current_prompt = current_file.read_text()

    ver_num = int(current_version.lstrip("v"))
    next_version = f"v{ver_num + 1:03d}"
    next_file = PROMPTS_DIR / f"screener_{next_version}.md"

    evolution_prompt = f"""아래는 주식 정배열 스크리너 프롬프트의 현재 버전과 Discriminator의 피드백이다.
피드백을 반영하여 개선된 다음 버전 프롬프트를 생성해.

## 현재 프롬프트 ({current_version})
```
{current_prompt}
```

## Discriminator 피드백
개선 제안:
{json.dumps(disc_result.get('prompt_improvements', []), ensure_ascii=False, indent=2)}

다음 버전 포커스: {disc_result.get('next_version_focus', 'N/A')}

적중 패턴: {json.dumps(disc_result.get('hits', []), ensure_ascii=False)}
실패 패턴: {json.dumps(disc_result.get('misses', []), ensure_ascii=False)}
놓친 패턴: {json.dumps(disc_result.get('overlooked', []), ensure_ascii=False)}

## 과교정 방지 규칙 (반드시 지켜라)
1. 한번에 최대 2개 조건만 추가/강화. 나머지는 유지.
2. "10종목 입력 시 최소 3종목 이상 분석 결과 출력" 하한선 유지.
3. 적중(hits) 규칙은 절대 제거 금지.
4. JSON 출력에 반드시 "code", "name", "conviction", "score" 필드 포함.
5. 새 카테고리/필드 추가는 사이클당 최대 1개.
6. 프롬프트 총 길이 50줄 이내. 간결하게.

## 출력
개선된 프롬프트만 출력. 앞뒤 설명, 마크다운 코드블록 없이.
"""

    output = _call_claude(evolution_prompt, timeout=120)

    # 마크다운 코드블록 제거
    if output.startswith("```"):
        lines = output.split("\n")
        output = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])

    next_file.write_text(output)
    print(f"\n프롬프트 진화: {current_version} → {next_version}")
    print(f"저장: {next_file}")
    return next_version


# ── 사이클 실행 ───────────────────────────────────────────

def run_cycle(screen_date, snapshots, stocks_data, check_days, prompt_version):
    """G → D 한 사이클 (샘플은 외부에서 주입)."""
    print(f"\n{'='*60}")
    print(f" 진화 사이클: {screen_date} | 검증 {check_days}일 | 프롬프트 {prompt_version}")
    print(f"{'='*60}")

    # Generator 실행
    print(f"[G] Generator 실행 중...")
    gen_results = run_generator(stocks_data, prompt_version)
    gen_results = [r for r in gen_results if isinstance(r, dict) and "code" in r]
    gen_codes = {r["code"] for r in gen_results}
    high_conv = [r for r in gen_results if r.get("conviction") == "high"]
    print(f"  → {len(gen_results)}종목 분석, conviction high: {len(high_conv)}종목")

    # 실제 결과 확인
    print(f"[D] {check_days}일 후 실제 결과 확인...")
    actual = {}
    for code, d in snapshots.items():
        future = check_future(code, screen_date, check_days)
        if future:
            actual[code] = {
                "code": code,
                "name": d["stock"]["name"],
                "was_aligned": d["snapshot"]["ma"]["aligned"],
                **future,
                "gen_selected": code in gen_codes,
                "gen_conviction": next(
                    (r.get("conviction") for r in gen_results if r["code"] == code), None
                ),
            }

    maintained = sum(1 for a in actual.values() if a["maintained"])
    overlooked = [a for a in actual.values() if not a["gen_selected"] and a["maintained"]]
    print(f"  → 정배열 유지: {maintained}/{len(actual)} | 놓침: {len(overlooked)}")

    # Discriminator 실행
    print(f"[E] Discriminator 실행 중...")
    disc_result = run_discriminator(gen_results, list(actual.values()), overlooked)

    # 스코어 계산
    selected_maintained = sum(
        1 for a in actual.values() if a["gen_selected"] and a["maintained"]
    )
    selected_total = sum(1 for a in actual.values() if a["gen_selected"])
    precision = selected_maintained / selected_total if selected_total else 0
    recall = selected_maintained / maintained if maintained else 0

    # 결과 저장
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    cycle_result = {
        "screen_date": screen_date,
        "check_days": check_days,
        "prompt_version": prompt_version,
        "sample_size": len(snapshots),
        "metrics": {
            "selected": selected_total,
            "high_conviction": len(high_conv),
            "maintained": maintained,
            "overlooked": len(overlooked),
            "precision": round(precision, 2),
            "recall": round(recall, 2),
        },
        "generator": gen_results,
        "actual": list(actual.values()),
        "discriminator": disc_result,
    }
    out_file = RESULTS_DIR / f"{screen_date}_{prompt_version}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(cycle_result, f, ensure_ascii=False, indent=2)

    return cycle_result


def print_cycle_summary(result):
    """사이클 결과 요약."""
    m = result["metrics"]
    v = result["prompt_version"]
    print(f"  {v}: 선별 {m['selected']}(high {m['high_conviction']}) | "
          f"유지 {m['maintained']} | 놓침 {m['overlooked']} | "
          f"P={m['precision']:.0%} R={m['recall']:.0%}")


# ── compare 모드 ──────────────────────────────────────────

def run_compare(screen_date, sample_size, check_days, versions, seed):
    """동일 샘플로 여러 프롬프트 버전 A/B 비교."""
    print(f"\n{'='*60}")
    print(f" A/B 비교: {screen_date} | seed={seed} | 버전: {', '.join(versions)}")
    print(f"{'='*60}")

    # 공통 샘플 생성
    universe = get_universe(screen_date)
    _, snapshots = sample_and_snapshot(universe, screen_date, sample_size, seed)
    stocks_data = "\n\n".join(
        format_for_prompt(d["stock"], d["snapshot"])
        for d in snapshots.values()
    )
    codes = list(snapshots.keys())
    print(f"\n공통 샘플: {len(snapshots)}종목 — {', '.join(codes)}")

    # 정답(실제 결과) 미리 계산
    actual_maintained = set()
    for code, d in snapshots.items():
        future = check_future(code, screen_date, check_days)
        if future and future["maintained"]:
            actual_maintained.add(code)
    print(f"실제 정배열 유지: {len(actual_maintained)}종목 — {', '.join(actual_maintained)}\n")

    # 각 버전 Generator 병렬 실행
    from concurrent.futures import ThreadPoolExecutor, as_completed
    valid_versions = [v for v in versions if (PROMPTS_DIR / f"screener_{v}.md").exists()]
    print(f"Generator 병렬 실행: {', '.join(valid_versions)}...")

    def _run_gen(v):
        gen = run_generator(stocks_data, v)
        return v, [r for r in gen if isinstance(r, dict) and "code" in r]

    gen_map = {}
    with ThreadPoolExecutor(max_workers=len(valid_versions)) as ex:
        futs = {ex.submit(_run_gen, v): v for v in valid_versions}
        for fut in as_completed(futs):
            v, gen = fut.result()
            gen_map[v] = gen
            high = sum(1 for r in gen if r.get("conviction") == "high")
            print(f"  {v}: {len(gen)}종목 (high {high})")

    # 실제 결과 + 메트릭 계산 (D 스킵)
    results = []
    for v in valid_versions:
        gen_results = gen_map[v]
        gen_codes = {r["code"] for r in gen_results}
        actual = {}
        for code, d in snapshots.items():
            future = check_future(code, screen_date, check_days)
            if future:
                actual[code] = {
                    "code": code, "name": d["stock"]["name"],
                    "was_aligned": d["snapshot"]["ma"]["aligned"],
                    **future,
                    "gen_selected": code in gen_codes,
                }
        sel_ok = sum(1 for a in actual.values() if a["gen_selected"] and a["maintained"])
        sel_total = sum(1 for a in actual.values() if a["gen_selected"])
        maintained = sum(1 for a in actual.values() if a["maintained"])
        overlooked = sum(1 for a in actual.values() if not a["gen_selected"] and a["maintained"])
        results.append({
            "prompt_version": v,
            "metrics": {
                "selected": sel_total,
                "high_conviction": sum(1 for r in gen_results if r.get("conviction") == "high"),
                "maintained": maintained,
                "overlooked": overlooked,
                "precision": round(sel_ok / sel_total, 2) if sel_total else 0,
                "recall": round(sel_ok / maintained, 2) if maintained else 0,
            },
        })

    # 비교 테이블
    print(f"\n{'='*60}")
    print(f" 비교 결과 ({screen_date}, seed={seed})")
    print(f"{'='*60}")
    print(f" 정답: {len(actual_maintained)}종목 정배열 유지")
    print(f"{'─'*60}")
    print(f" {'버전':<6} {'선별':>4} {'high':>4} {'적중':>4} {'놓침':>4} {'정밀도':>6} {'재현율':>6}")
    print(f"{'─'*60}")
    for r in results:
        m = r["metrics"]
        print(f" {r['prompt_version']:<6} {m['selected']:4d} {m['high_conviction']:4d} "
              f"{m['selected'] - m['overlooked']:4d} {m['overlooked']:4d} "
              f"{m['precision']:6.0%} {m['recall']:6.0%}")

    return results


# ── 진화 모드 ─────────────────────────────────────────────

def run_evolve(start_date, sample_size, check_days, start_version, cycles, seed):
    """연속 진화 사이클."""
    dates = get_trading_dates("2025-06-01", "2025-12-31")
    start_idx = 0
    for i, d in enumerate(dates):
        if d >= start_date:
            start_idx = i
            break

    version = start_version
    for cycle in range(cycles):
        idx = start_idx + cycle * 20
        if idx >= len(dates):
            print(f"\n거��일 부족으로 {cycle}사이클에서 중단")
            break
        date = dates[idx]

        universe = get_universe(date)
        _, snapshots = sample_and_snapshot(universe, date, sample_size, seed + cycle if seed else None)
        stocks_data = "\n\n".join(
            format_for_prompt(d["stock"], d["snapshot"])
            for d in snapshots.values()
        )
        print(f"\n[사이클 {cycle+1}/{cycles}] 샘플: {len(snapshots)}종목")

        result = run_cycle(date, snapshots, stocks_data, check_days, version)
        print_cycle_summary(result)

        if result.get("discriminator"):
            version = evolve_prompt(version, result["discriminator"])
            print(f"다음 사이클: {version}\n")


# ─�� main ──────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="스크리너 진화 시스템")
    sub = parser.add_subparsers(dest="mode", required=True)

    # evolve 모드
    p_evolve = sub.add_parser("evolve", help="연속 진화 사이클")
    p_evolve.add_argument("--date", default="2025-10-01")
    p_evolve.add_argument("--sample", type=int, default=10)
    p_evolve.add_argument("--check-days", type=int, default=20)
    p_evolve.add_argument("--prompt", default="v001")
    p_evolve.add_argument("--cycles", type=int, default=3)
    p_evolve.add_argument("--seed", type=int, default=42)

    # compare 모드
    p_compare = sub.add_parser("compare", help="동일 샘플 버전 비교")
    p_compare.add_argument("--date", default="2025-10-01")
    p_compare.add_argument("--sample", type=int, default=15)
    p_compare.add_argument("--check-days", type=int, default=20)
    p_compare.add_argument("--versions", nargs="+", default=["v001", "v002", "v003"])
    p_compare.add_argument("--seed", type=int, default=42)

    args = parser.parse_args()

    if args.mode == "evolve":
        run_evolve(args.date, args.sample, args.check_days, args.prompt, args.cycles, args.seed)
    elif args.mode == "compare":
        run_compare(args.date, args.sample, args.check_days, args.versions, args.seed)

"""5종목 × 5년 백테스트 진화 루프. tmux에서 실행."""

import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import market_db as db

PROJECT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = PROJECT / "prompts"
RESULTS_DIR = PROJECT / "data" / "screener-evolve"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

STOCKS = [
    ("005930", "삼성전자", "반도체"),
    ("105560", "KB금융", "금융"),
    ("068270", "셀트리온", "바이오"),
    ("009540", "HD한국조선해양", "조선"),
    ("069500", "KODEX 200", "ETF"),
]


def compute_ma(code, date):
    prices = db._query(
        "SELECT close FROM daily_prices WHERE code=? AND date<=? ORDER BY date DESC LIMIT 120",
        [code, date],
    )
    if len(prices) < 120:
        return None
    c = [p["close"] for p in reversed(prices)]
    ma5, ma20, ma60, ma120 = sum(c[-5:])/5, sum(c[-20:])/20, sum(c[-60:])/60, sum(c[-120:])/120
    aligned = ma5 > ma20 > ma60 > ma120
    semi = ma5 > ma20 > ma60 and ma60 <= ma120
    return {
        "ma5": round(ma5), "ma20": round(ma20), "ma60": round(ma60), "ma120": round(ma120),
        "aligned": aligned, "semi": semi, "close": c[-1],
    }


def snapshot(code, date):
    ma = compute_ma(code, date)
    if not ma:
        return None
    prices = db._query(
        "SELECT date, close, volume, change_rate FROM daily_prices WHERE code=? AND date<=? ORDER BY date DESC LIMIT 5",
        [code, date],
    )
    flow = db._query(
        "SELECT foreign_net, institution_net FROM investor_flow WHERE code=? AND date<=? ORDER BY date DESC LIMIT 10",
        [code, date],
    )
    val = db._query(
        "SELECT per, pbr FROM daily_valuations WHERE code=? AND date<=? ORDER BY date DESC LIMIT 1",
        [code, date],
    )
    return {
        "ma": ma,
        "prices": [{"d": p["date"], "c": p["close"], "chg": p["change_rate"] or 0} for p in prices],
        "flow": {"fgn": sum(f["foreign_net"] or 0 for f in flow), "inst": sum(f["institution_net"] or 0 for f in flow)},
        "val": dict(val[0]) if val else {},
    }


def format_stock(code, name, sector, snap):
    ma = snap["ma"]
    st = "정배열" if ma["aligned"] else ("준정배열" if ma["semi"] else "역배열")
    lines = [f"### {code} {name} | {sector}"]
    lines.append(f"MA: {st} | 5={ma['ma5']:,} 20={ma['ma20']:,} 60={ma['ma60']:,} 120={ma['ma120']:,} | 종가={ma['close']:,}")
    if snap["prices"]:
        lines.append("5일: " + " | ".join(f"{p['d'][-5:]}:{p['c']:,}({p['chg']:+.1f}%)" for p in snap["prices"]))
    fl = snap["flow"]
    lines.append(f"수급10일: 외인={fl['fgn']:+,.0f} 기관={fl['inst']:+,.0f}")
    v = snap["val"]
    if v:
        lines.append(f"PER={v.get('per','N/A')} PBR={v.get('pbr','N/A')}")
    return "\n".join(lines)


def check_future(code, date, days=20):
    dates = db._query(
        "SELECT DISTINCT date FROM daily_prices WHERE date > ? ORDER BY date LIMIT ?",
        [date, days],
    )
    if len(dates) < days:
        return None
    aligned_days = 0
    last_close = None
    for d in dates:
        ma = compute_ma(code, d["date"])
        if ma:
            if ma["aligned"]:
                aligned_days += 1
            last_close = ma["close"]
    first_ma = compute_ma(code, date)
    ret = ((last_close / first_ma["close"]) - 1) * 100 if first_ma and last_close else None
    return {
        "aligned_days": aligned_days,
        "ratio": round(aligned_days / days, 2),
        "maintained": aligned_days >= days * 0.8,
        "return_pct": round(ret, 2) if ret else None,
    }


def call_claude(prompt, system_file=None, timeout=120):
    cmd = ["claude", "-p", prompt, "--allowedTools", "", "--max-turns", "1", "--output-format", "text"]
    if system_file:
        cmd += ["--append-system-prompt-file", str(system_file)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(PROJECT))
        out = r.stdout.strip()
        return "" if out.startswith("Error:") else out
    except subprocess.TimeoutExpired:
        return ""


def parse_json_array(text):
    if not text:
        return []
    # try {selected:[...]}
    s = text.find("{")
    e = text.rfind("}")
    if s >= 0 and e > s:
        try:
            obj = json.loads(text[s:e+1])
            if isinstance(obj, dict) and "selected" in obj:
                return obj["selected"]
        except json.JSONDecodeError:
            pass
    # try [...]
    s = text.find("[")
    e = text.rfind("]")
    if s >= 0 and e > s:
        try:
            return json.loads(text[s:e+1])
        except json.JSONDecodeError:
            pass
    return []


def run_backtest(version="v002", max_cycles=10):
    """5종목 × 월별 날짜로 G→D 축적, 일정 횟수마다 진화."""
    # 월별 거래일 추출 (2022-01 ~ 2025-09, 검증 20일 필요하므로)
    all_dates = db._query(
        "SELECT DISTINCT date FROM daily_prices WHERE date BETWEEN '2022-06-01' AND '2025-09-30' ORDER BY date"
    )
    # 월 1회 (매월 첫 거래일)
    monthly = []
    seen_month = set()
    for d in all_dates:
        ym = d["date"][:7]
        if ym not in seen_month:
            seen_month.add(ym)
            monthly.append(d["date"])
    print(f"테스트 날짜: {len(monthly)}개 ({monthly[0]} ~ {monthly[-1]})")
    print(f"종목: {', '.join(n for _,n,_ in STOCKS)}")
    print(f"시작 프롬프트: {version}\n")

    cycle = 0
    all_feedback = []
    results_log = []

    for date in monthly:
        # 스냅샷 수집
        stock_texts = []
        snaps = {}
        for code, name, sector in STOCKS:
            s = snapshot(code, date)
            if s:
                snaps[code] = s
                stock_texts.append(format_stock(code, name, sector, s))

        if not stock_texts:
            continue

        # Generator
        prompt = "## 분석 대상\n\n" + "\n\n".join(stock_texts) + "\n\nJSON만 출력."
        prompt_file = PROMPTS_DIR / f"screener_{version}.md"
        gen_out = call_claude(prompt, system_file=prompt_file)
        gen_results = parse_json_array(gen_out)
        gen_results = [r for r in gen_results if isinstance(r, dict) and "code" in r]
        gen_codes = {r["code"] for r in gen_results}
        high = [r for r in gen_results if r.get("conviction") == "high"]

        # 실제 결과
        actuals = {}
        for code, name, sector in STOCKS:
            if code not in snaps:
                continue
            fut = check_future(code, date)
            if fut:
                actuals[code] = {
                    "code": code, "name": name,
                    "was_aligned": snaps[code]["ma"]["aligned"],
                    "selected": code in gen_codes,
                    "conviction": next((r.get("conviction") for r in gen_results if r["code"] == code), None),
                    **fut,
                }

        maintained = [a for a in actuals.values() if a["maintained"]]
        selected_ok = [a for a in actuals.values() if a["selected"] and a["maintained"]]
        overlooked = [a for a in actuals.values() if not a["selected"] and a["maintained"]]
        sel_total = sum(1 for a in actuals.values() if a["selected"])
        precision = len(selected_ok) / sel_total if sel_total else 0
        recall = len(selected_ok) / len(maintained) if maintained else 0

        row = {
            "date": date, "version": version,
            "selected": sel_total, "high": len(high),
            "maintained": len(maintained), "overlooked": len(overlooked),
            "precision": round(precision, 2), "recall": round(recall, 2),
            "details": actuals,
        }
        results_log.append(row)
        print(f"{date} [{version}] 선별={sel_total} high={len(high)} "
              f"유지={len(maintained)}/5 놓침={len(overlooked)} P={precision:.0%} R={recall:.0%}")

        # Discriminator (5회마다)
        cycle += 1
        if cycle % 5 == 0 and cycle <= max_cycles * 5:
            print(f"\n  --- D 실행 (최근 5회 피드백) ---")
            recent = results_log[-5:]
            disc_data = (
                f"## 최근 5회 Generator 결과 요약\n"
                + "\n".join(
                    f"- {r['date']}: 선별{r['selected']} 유지{r['maintained']} P={r['precision']:.0%} R={r['recall']:.0%}"
                    for r in recent
                )
                + f"\n\n## 상세 결과\n```json\n{json.dumps([r['details'] for r in recent], ensure_ascii=False, indent=1)}\n```"
                + f"\n\nJSON만 출력."
            )
            disc_out = call_claude(disc_data, system_file=PROMPTS_DIR / "discriminator_v001.md")
            ds = disc_out.find("{")
            de = disc_out.rfind("}")
            disc_result = {}
            if ds >= 0 and de > ds:
                try:
                    disc_result = json.loads(disc_out[ds:de+1])
                except json.JSONDecodeError:
                    pass

            if disc_result.get("prompt_improvements"):
                print(f"  D 개선 제안:")
                for imp in disc_result["prompt_improvements"][:3]:
                    print(f"    - {imp[:80]}")

            # 진화
            cur_prompt = prompt_file.read_text()
            ver_num = int(version.lstrip("v"))
            new_version = f"v{ver_num + 1:03d}"

            evo_prompt = f"""현재 프롬프트 ({version}):
```
{cur_prompt}
```

D 피드백:
{json.dumps(disc_result.get('prompt_improvements', []), ensure_ascii=False)}
포커스: {disc_result.get('next_version_focus', 'N/A')}

규칙: 50줄 이내. code/name/conviction/score 필드 유지. 한번에 2개 조건만 변경. 프롬프트만 출력."""

            evo_out = call_claude(evo_prompt)
            if evo_out and len(evo_out) > 100:
                if evo_out.startswith("```"):
                    lines = evo_out.split("\n")
                    evo_out = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
                new_file = PROMPTS_DIR / f"screener_{new_version}.md"
                new_file.write_text(evo_out)
                version = new_version
                print(f"  진화: → {version} ({new_file.stat().st_size}bytes)")
            print()

    # 최종 요약
    out_file = RESULTS_DIR / f"backtest_full.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results_log, f, ensure_ascii=False, indent=2)
    print(f"\n{'='*60}")
    print(f" 백테스트 완료: {len(results_log)}회")
    print(f"{'='*60}")

    # 버전별 집계
    by_ver = {}
    for r in results_log:
        v = r["version"]
        if v not in by_ver:
            by_ver[v] = {"count": 0, "p_sum": 0, "r_sum": 0}
        by_ver[v]["count"] += 1
        by_ver[v]["p_sum"] += r["precision"]
        by_ver[v]["r_sum"] += r["recall"]

    print(f"\n{'버전':<8} {'횟수':>4} {'평균P':>6} {'평균R':>6}")
    print(f"{'─'*30}")
    for v, s in by_ver.items():
        n = s["count"]
        print(f"{v:<8} {n:4d} {s['p_sum']/n:6.0%} {s['r_sum']/n:6.0%}")

    print(f"\n저장: {out_file}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", default="v002")
    parser.add_argument("--max-cycles", type=int, default=8, help="최대 진화 횟수")
    args = parser.parse_args()
    run_backtest(args.prompt, args.max_cycles)

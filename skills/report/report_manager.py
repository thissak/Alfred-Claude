"""장마감 리포트 매니저 — Claude 호출 + 노션 저장 + 폴백.

trigger.sh 대신 이 스크립트를 launchd에서 실행.
1. Claude -p 호출 (timeout 5분)
2. 출력에서 리포트 파싱
3. 노션 DB에 저장
4. 실패 시 outbox에 iMessage 폴백
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent.parent
LOG_DIR = PROJECT / "run" / "logs"
REPORT_DIR = PROJECT / "run" / "reports"
OUTBOX_DIR = PROJECT / "run" / "outbox"

CLAUDE = os.path.expanduser("~/.local/bin/claude")
SYSTEM_PROMPT = PROJECT / "skills" / "report" / "system.md"

NOTION_PAGE_PARENT = "336b83e1-2dd9-8124-9f20-f42c988506ec"  # 장마감 리포트 폴더 page_id

CLAUDE_TIMEOUT = 420  # 7분
NOTION_TIMEOUT = 30


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def run_claude():
    """Claude 에이전트로 리포트 생성. 타임아웃 적용."""
    log("Claude 리포트 생성 시작")
    try:
        result = subprocess.run(
            [CLAUDE, "--dangerously-skip-permissions",
             "--model", "sonnet",
             "--system-prompt-file", str(SYSTEM_PROMPT),
             "-p", "장 마감 리포트를 생성해줘. 노션 저장은 하지 마. run/reports/에 md 파일만 저장해."],
            capture_output=True, text=True,
            timeout=CLAUDE_TIMEOUT,
            cwd=str(PROJECT),
            env={**os.environ, "PATH": "/opt/homebrew/bin:/Users/afred/.local/bin:/usr/local/bin:/usr/bin:/bin"},
        )
        log(f"Claude 완료 (exit={result.returncode})")
        return result.stdout, result.returncode == 0
    except subprocess.TimeoutExpired:
        log(f"Claude 타임아웃 ({CLAUDE_TIMEOUT}초)")
        return "", False


def find_latest_report():
    """가장 최근 리포트 파일 찾기."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    report_file = REPORT_DIR / f"{today}.md"
    if report_file.exists():
        return report_file
    # 오늘 날짜 파일이 없으면 가장 최근 파일
    reports = sorted(REPORT_DIR.glob("*.md"), reverse=True)
    return reports[0] if reports else None


def parse_report(report_path):
    """리포트 MD에서 주요 정보 추출."""
    content = report_path.read_text()
    info = {
        "title": "",
        "kospi": None,
        "kosdaq": None,
        "content": content,
    }

    for line in content.split("\n"):
        if line.startswith("# 장 마감 리포트"):
            info["title"] = line.lstrip("# ").strip()
        # 테이블에서 KOSPI/KOSDAQ 추출
        if "KOSPI" in line and "|" in line and "지수" not in line and "등락" not in line:
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if len(parts) >= 2:
                try:
                    info["kospi"] = float(parts[1].replace(",", ""))
                except (ValueError, IndexError):
                    pass
        if "KOSDAQ" in line and "|" in line and "지수" not in line and "등락" not in line:
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if len(parts) >= 2:
                try:
                    info["kosdaq"] = float(parts[1].replace(",", ""))
                except (ValueError, IndexError):
                    pass

    return info


def save_to_notion(info, market_signal, aligned_pct):
    """노션 장마감 리포트 폴더에 개별 페이지로 저장. Claude MCP 경유."""
    today = datetime.now().strftime("%Y-%m-%d")
    title = info.get("title") or f"장 마감 리포트 ({datetime.now().strftime('%-m/%d')})"

    # 리포트 내용을 노션 마크다운으로 간소화 (3000자 제한)
    content = _md_to_notion(info["content"])

    notion_prompt = f"""노션 DB에 페이지를 생성해. notion-create-pages 도구를 사용해.
다른 작업은 절대 하지 마. 도구 호출만 해.

parent: page_id = {NOTION_PAGE_PARENT}
properties:
  title: "{title}"
icon: "📊" 

content:
{content}
"""

    try:
        result = subprocess.run(
            [CLAUDE, "--dangerously-skip-permissions",
             "--model", "haiku",
             "--allowedTools", "mcp__claude_ai_Notion__notion-create-pages",
             "--max-turns", "3",
             "-p", notion_prompt],
            capture_output=True, text=True,
            timeout=90,
            cwd=str(PROJECT),
            env={**os.environ, "PATH": "/opt/homebrew/bin:/Users/afred/.local/bin:/usr/local/bin:/usr/bin:/bin"},
        )
        output = result.stdout
        if result.returncode == 0 and ("notion.so" in output or "페이지" in output or "page" in output.lower()):
            log("노션 저장 성공")
            return True
        log(f"노션 저장 실패 (exit={result.returncode}): {output[:300]}")
    except subprocess.TimeoutExpired:
        log("노션 저장 타임아웃 (90초)")

    return False


def _md_to_notion(md_content):
    """리포트 MD를 노션 호환 형태로 정리 (테이블 → 텍스트)."""
    lines = []
    for line in md_content.split("\n"):
        # MD 테이블은 노션에서 지원 안 됨 → 텍스트로 변환
        if line.strip().startswith("|") and "---" not in line:
            cells = [c.strip() for c in line.strip("|").split("|") if c.strip()]
            lines.append("  ".join(cells))
        elif "---" in line and "|" in line:
            continue  # 테이블 구분선 스킵
        else:
            lines.append(line)
    result = "\n".join(lines)
    # 3000자 제한
    if len(result) > 3000:
        result = result[:2950] + "\n\n... (이하 생략)"
    return result


def fallback_imessage(info):
    """iMessage 폴백 — outbox에 JSON 저장."""
    OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    summary = info["content"][:500] if info.get("content") else "리포트 생성 실패"

    msg = {
        "recipient": "me",
        "message": f"📊 {info.get('title', '장마감 리포트')}\n\n{summary}\n\n(노션 저장 실패 — iMessage 폴백)",
    }
    out_file = OUTBOX_DIR / f"report-{today}.json"
    with open(out_file, "w") as f:
        json.dump(msg, f, ensure_ascii=False, indent=2)
    log(f"iMessage 폴백: {out_file}")


def get_market_signal():
    """현재 시장 타이밍 시그널 (간이 버전)."""
    try:
        sys.path.insert(0, str(PROJECT / "src"))
        import market_db as db

        # 최신 거래일
        row = db._query("SELECT MAX(date) d FROM daily_prices WHERE volume > 0")
        latest = row[0]["d"] if row else None
        if not latest:
            return "NEUTRAL", 0

        # 정배열 비율 — screener_rl 데이터셋에서 최신 날짜 참조 (빠름)
        # 없으면 market_breadth.csv에서
        import pandas as pd
        breadth_file = PROJECT / "data" / "market_breadth.csv"
        if breadth_file.exists():
            mb = pd.read_csv(breadth_file)
            mb = mb[mb["date"] <= latest].sort_values("date")
            if not mb.empty:
                row = mb.iloc[-1]
                pct = row.get("pct_aligned", 0)
                if pct < 0.05:
                    return "BUY", round(pct, 4)
                elif 0.05 <= pct < 0.15:
                    return "CASH", round(pct, 4)
                elif 0.25 <= pct <= 0.40:
                    return "BUY", round(pct, 4)
                elif pct > 0.40:
                    return "CASH", round(pct, 4)
                else:
                    return "NEUTRAL", round(pct, 4)

        # fallback: 간이 계산
        aligned = db._query(f"""
            SELECT COUNT(*) total,
                   SUM(CASE WHEN ma5 > ma20 AND ma20 > ma60 AND ma60 > ma120 THEN 1 ELSE 0 END) aligned
            FROM (
                SELECT dp.code,
                    AVG(CASE WHEN rn <= 5 THEN dp.close END) as ma5,
                    AVG(CASE WHEN rn <= 20 THEN dp.close END) as ma20,
                    AVG(CASE WHEN rn <= 60 THEN dp.close END) as ma60,
                    AVG(CASE WHEN rn <= 120 THEN dp.close END) as ma120
                FROM (
                    SELECT dp.code, dp.close,
                        ROW_NUMBER() OVER (PARTITION BY dp.code ORDER BY dp.date DESC) rn
                    FROM daily_prices dp
                    JOIN securities s ON s.code = dp.code
                    WHERE dp.date <= '{latest}'
                      AND s.is_etp=0 AND s.is_spac=0 AND s.is_halt=0 AND s.is_admin=0
                      AND dp.volume > 0 AND length(s.code) <= 6
                ) dp WHERE rn <= 120
                GROUP BY dp.code
                HAVING COUNT(*) >= 120
            )
        """)
        if not aligned:
            return "NEUTRAL", 0

        total = aligned[0]["total"]
        al = aligned[0]["aligned"]
        pct = al / total if total > 0 else 0

        if pct < 0.05:
            return "BUY", round(pct, 4)
        elif 0.05 <= pct < 0.15:
            return "CASH", round(pct, 4)
        elif 0.25 <= pct <= 0.40:
            return "BUY", round(pct, 4)
        elif pct > 0.40:
            return "CASH", round(pct, 4)
        else:
            return "NEUTRAL", round(pct, 4)

    except Exception as e:
        log(f"시장 시그널 계산 실패: {e}")
        return "NEUTRAL", 0


def main():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y%m%d")
    log_file = LOG_DIR / f"report-{today}.log"

    # stdout/stderr를 로그 파일로
    import io
    tee = open(log_file, "a")
    class Tee:
        def __init__(self, *files):
            self.files = files
        def write(self, data):
            for f in self.files:
                f.write(data)
                f.flush()
        def flush(self):
            for f in self.files:
                f.flush()
    sys.stdout = Tee(sys.stdout, tee)
    sys.stderr = Tee(sys.stderr, tee)

    log("=" * 50)
    log("장마감 리포트 매니저 시작")

    # 1. 시장 시그널
    signal, pct = get_market_signal()
    log(f"시장 시그널: {signal} (정배열 {pct:.1%})")

    # 2. 주말 체크 (토=5, 일=6)
    if datetime.now().weekday() in (5, 6):
        log("주말 — 장 미개장, 스킵")
        return

    # 3. Claude로 리포트 생성
    output, success = run_claude()

    # 4. 리포트 파일 찾기 (타임아웃이어도 파일이 생성됐을 수 있음)
    report = find_latest_report()
    today_str = datetime.now().strftime("%Y-%m-%d")
    if report and report.name == f"{today_str}.md":
        log(f"리포트 파일 확인: {report.name}" + (" (타임아웃 후 복구)" if not success else ""))
    elif not success:
        log("Claude 리포트 생성 실패 — 파일도 없음")
        fallback_imessage({"title": "장마감 리포트", "content": "리포트 생성 실패 (타임아웃)"})
        return
    elif not report:
        log("리포트 파일 없음")
        fallback_imessage({"title": "장마감 리포트", "content": output[:500]})
        return

    info = parse_report(report)
    log(f"리포트 파싱: {info['title']} KOSPI={info['kospi']} KOSDAQ={info['kosdaq']}")

    # 4. 노션 저장
    saved = save_to_notion(info, signal, pct)
    if not saved:
        log("노션 저장 실패 → iMessage 폴백")
        fallback_imessage(info)
    else:
        log("노션 저장 완료")

    log("장마감 리포트 매니저 완료")
    log("=" * 50)


if __name__ == "__main__":
    main()

"""Daily Surge 스크리닝 매니저 — 스크리너 실행 + 노션 저장.

launchd에서 매일 16:10에 실행.
1. daily_surge_screener.py 실행
2. 결과 JSON 읽기
3. 노션 "Daily Surge 스크리닝" 폴더에 개별 페이지 저장
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent.parent
LOG_DIR = PROJECT / "run" / "logs"
DATA_DIR = PROJECT / "data"

CLAUDE = os.path.expanduser("~/.local/bin/claude")
SCREENER = PROJECT / "scripts" / "daily_surge_screener.py"

NOTION_PAGE_PARENT = "336b83e1-2dd9-8141-b56f-c86bf06a33fb"  # Daily Surge 스크리닝 폴더

SCREENER_TIMEOUT = 120  # 2분
NOTION_TIMEOUT = 90


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def run_screener(date_str=None):
    """daily_surge_screener.py 실행."""
    cmd = ["python3", str(SCREENER)]
    if date_str:
        cmd.append(date_str)

    log(f"스크리너 실행: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True, text=True,
            timeout=SCREENER_TIMEOUT,
            cwd=str(PROJECT),
            env={**os.environ, "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"},
        )
        log(f"스크리너 완료 (exit={result.returncode})")
        if result.returncode != 0:
            log(f"stderr: {result.stderr[:500]}")
        return result.stdout, result.returncode == 0
    except subprocess.TimeoutExpired:
        log(f"스크리너 타임아웃 ({SCREENER_TIMEOUT}초)")
        return "", False


def find_surge_json(date_str=None):
    """스크리닝 결과 JSON 찾기."""
    if date_str:
        f = DATA_DIR / f"daily_surge_{date_str}.json"
        return f if f.exists() else None

    # 오늘 날짜로 시도
    today = datetime.now().strftime("%Y-%m-%d")
    f = DATA_DIR / f"daily_surge_{today}.json"
    if f.exists():
        return f

    # 가장 최근 파일
    files = sorted(DATA_DIR.glob("daily_surge_*.json"), reverse=True)
    return files[0] if files else None


def save_to_notion(surge_data, terminal_output):
    """노션 Daily Surge 폴더에 개별 페이지로 저장."""
    date_str = surge_data.get("date", datetime.now().strftime("%Y-%m-%d"))
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    title = f"Daily Surge ({dt.strftime('%-m/%d')})"

    # 터미널 출력을 노션 콘텐츠로 사용 (3000자 제한)
    content = terminal_output[:3000] if terminal_output else json.dumps(surge_data, ensure_ascii=False, indent=2)[:3000]

    notion_prompt = f"""노션에 페이지를 생성해. notion-create-pages 도구를 사용해.
다른 작업은 절대 하지 마. 도구 호출만 해.

parent: page_id = {NOTION_PAGE_PARENT}
properties:
  title: "{title}"
icon: "🔥"

content (Notion Markdown으로 변환해서 넣어. 테이블은 <table header-row="true"> 형식 사용):
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
            timeout=NOTION_TIMEOUT,
            cwd=str(PROJECT),
            env={**os.environ, "PATH": "/opt/homebrew/bin:/Users/afred/.local/bin:/usr/local/bin:/usr/bin:/bin"},
        )
        output = result.stdout
        if result.returncode == 0 and ("notion.so" in output or "페이지" in output or "page" in output.lower()):
            log("노션 저장 성공")
            return True
        log(f"노션 저장 실패 (exit={result.returncode}): {output[:300]}")
    except subprocess.TimeoutExpired:
        log("노션 저장 타임아웃")

    return False


def main():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y%m%d")
    log_file = LOG_DIR / f"surge-{today}.log"

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
    log("Daily Surge 매니저 시작")

    # 1. 스크리너 실행
    output, success = run_screener()
    if not success:
        log("스크리너 실패")
        return

    # 2. JSON 결과 읽기
    surge_file = find_surge_json()
    if not surge_file:
        log("스크리닝 결과 JSON 없음")
        return

    surge_data = json.loads(surge_file.read_text())
    log(f"스크리닝 결과: {surge_file.name} ({len(surge_data.get('events', []))}개 이벤트)")

    # 3. 노션 저장
    saved = save_to_notion(surge_data, output)
    if not saved:
        log("노션 저장 실패")
    else:
        log("노션 저장 완료")

    log("Daily Surge 매니저 완료")
    log("=" * 50)


if __name__ == "__main__":
    main()

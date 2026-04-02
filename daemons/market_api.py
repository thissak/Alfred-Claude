#!/usr/bin/env python3
"""market_api.py — market.db 읽기 전용 HTTP API + 데몬 대시보드.

맥프로에서 market.db에 접근하기 위한 경량 SQL 프록시.
POST /query {sql, params} → JSON 배열 반환. SELECT만 허용.
GET  /daemons             → 데몬 상태 HTML 대시보드
GET  /api/daemons         → 데몬 상태 JSON
"""

import json
import os
import sys
import time
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import src.market_db as db

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from heartbeat import beat

HOST = "0.0.0.0"
PORT = 8001

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HEARTBEAT_DIR = PROJECT_ROOT / "run" / "heartbeat"

# daemon_ctl.py와 동일한 데몬 목록
DAEMONS = {
    "bridge": "iMessage 브릿지",
    "inbox": "inbox 감시 + Claude 응답",
    "schedule": "스케줄 실행",
    "email": "네이버 이메일 IMAP",
    "collector": "주식 데이터 일일 수집",
    "trump": "트럼프 Truth Social RSS",
    "market-api": "market.db HTTP API",
    "buy-alert": "매수 타이밍 알림",
}

STALE_SECONDS = {
    "bridge": 10,       # 1초 폴링 → 10초 미응답이면 이상
    "inbox": 10,        # 2초 폴링
    "schedule": 10,     # 2초 폴링
    "email": 360,       # 5분 폴링
    "collector": 60,    # 30초 폴링
    "trump": 360,       # 5분 폴링
    "market-api": 30,   # 요청 기반
    "buy-alert": 60,    # 30초 폴링
}


def _read_heartbeats():
    """모든 데몬의 heartbeat 파일 읽기."""
    now = time.time()
    result = {}
    for name, desc in DAEMONS.items():
        path = HEARTBEAT_DIR / f"{name}.json"
        entry = {"name": name, "desc": desc, "alive": False, "status": "unknown",
                 "detail": "", "ts": None, "age": None}
        if path.exists():
            try:
                data = json.loads(path.read_text())
                mtime = path.stat().st_mtime
                age = now - mtime
                entry["ts"] = data.get("ts", "")
                entry["status"] = data.get("status", "unknown")
                entry["detail"] = data.get("detail", "")
                entry["age"] = round(age)
                entry["alive"] = age < STALE_SECONDS.get(name, 120)
            except Exception:
                pass
        result[name] = entry
    return result


DASHBOARD_HTML = """\
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Alf Daemons</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
         background: #0d1117; color: #c9d1d9; padding: 24px; }
  h1 { font-size: 1.4rem; margin-bottom: 16px; color: #58a6ff; }
  .meta { font-size: 0.8rem; color: #8b949e; margin-bottom: 20px; }
  table { width: 100%%; border-collapse: collapse; }
  th { text-align: left; padding: 8px 12px; color: #8b949e; font-size: 0.75rem;
       text-transform: uppercase; border-bottom: 1px solid #21262d; }
  td { padding: 10px 12px; border-bottom: 1px solid #21262d; font-size: 0.9rem; }
  tr:hover { background: #161b22; }
  .dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%%;
         margin-right: 8px; }
  .dot-ok { background: #3fb950; box-shadow: 0 0 6px #3fb950; }
  .dot-idle { background: #d29922; box-shadow: 0 0 6px #d29922; }
  .dot-error { background: #f85149; box-shadow: 0 0 6px #f85149; }
  .dot-dead { background: #484f58; }
  .age { color: #8b949e; font-size: 0.8rem; }
  .detail { color: #8b949e; font-size: 0.85rem; max-width: 300px;
            overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  @media (max-width: 600px) {
    body { padding: 12px; }
    td, th { padding: 6px 8px; font-size: 0.8rem; }
  }
</style>
</head>
<body>
<h1>Alf Daemon Dashboard</h1>
<div class="meta">Auto-refresh 5s &mdash; <span id="clock"></span></div>
<table>
<thead><tr><th>Status</th><th>Daemon</th><th>Description</th><th>Last Beat</th><th>Age</th><th>Detail</th></tr></thead>
<tbody id="tbody"></tbody>
</table>
<script>
async function refresh() {
  try {
    const r = await fetch('/api/daemons');
    const data = await r.json();
    const tbody = document.getElementById('tbody');
    tbody.innerHTML = '';
    for (const d of data) {
      const cls = !d.alive ? 'dead' : d.status === 'error' ? 'error' : d.status === 'idle' ? 'idle' : 'ok';
      const age = d.age !== null ? d.age + 's' : '-';
      tbody.innerHTML += `<tr>
        <td><span class="dot dot-${cls}"></span>${d.alive ? (d.status || 'ok') : 'offline'}</td>
        <td><strong>${d.name}</strong></td>
        <td>${d.desc}</td>
        <td>${d.ts || '-'}</td>
        <td class="age">${age}</td>
        <td class="detail" title="${d.detail || ''}">${d.detail || '-'}</td>
      </tr>`;
    }
  } catch(e) { console.error(e); }
  document.getElementById('clock').textContent = new Date().toLocaleTimeString();
}
refresh();
setInterval(refresh, 5000);
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/query":
            self._send(404, {"error": "not found"})
            return
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        sql = body.get("sql", "").strip()
        params = body.get("params", [])

        if not sql.upper().startswith("SELECT"):
            self._send(403, {"error": "read-only: SELECT only"})
            return

        try:
            conn = db._get_conn()
            rows = conn.execute(sql, params).fetchall()
            self._send(200, [dict(r) for r in rows])
        except Exception as e:
            self._send(500, {"error": str(e)})

    def do_GET(self):
        beat("market-api", "ok", f"GET {self.path}")
        if self.path == "/health":
            self._send(200, {"status": "ok"})
            return
        if self.path == "/api/daemons":
            hb = _read_heartbeats()
            self._send(200, list(hb.values()))
            return
        if self.path == "/daemons":
            self._send_html(200, DASHBOARD_HTML)
            return
        self._send(404, {"error": "not found"})

    def _send(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

    def _send_html(self, code, html):
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode())

    def log_message(self, fmt, *args):
        pass  # suppress access logs


if __name__ == "__main__":
    db.init()
    beat("market-api", "ok", "시작됨")
    server = HTTPServer((HOST, PORT), Handler)
    print(f"market-api listening on {HOST}:{PORT}")
    print(f"  dashboard: http://localhost:{PORT}/daemons")
    server.serve_forever()

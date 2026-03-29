#!/usr/bin/env python3
"""market_api.py — market.db 읽기 전용 HTTP API.

맥프로에서 market.db에 접근하기 위한 경량 SQL 프록시.
POST /query {sql, params} → JSON 배열 반환. SELECT만 허용.
"""

import json
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import src.market_db as db

HOST = "0.0.0.0"
PORT = 8001


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
        if self.path == "/health":
            self._send(200, {"status": "ok"})
            return
        self._send(404, {"error": "not found"})

    def _send(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

    def log_message(self, fmt, *args):
        pass  # suppress access logs


if __name__ == "__main__":
    db.init()
    server = HTTPServer((HOST, PORT), Handler)
    print(f"market-api listening on {HOST}:{PORT}")
    server.serve_forever()

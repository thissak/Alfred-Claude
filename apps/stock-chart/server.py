#!/usr/bin/env python3
"""stock-chart MVP 서버 — 종목 차트 데이터 API + 정적 프론트 서빙.

stdlib http.server 기반 (market_api.py와 동일 스타일, 의존성 0).
- GET /                       → web/index.html
- GET /api/ohlcv?code=&range= → 일봉 OHLCV (오름차순), 종목명 포함
- GET /api/search?q=          → 종목 검색 (code/name)

데이터는 src/market_db.py 경유. MARKET_DB_HOST 설정 시 원격 API,
미설정 시 로컬 market.db 직접 접근 (맥미니 기본).
"""

import json
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import src.market_db as db

HOST = os.environ.get("STOCK_CHART_HOST", "127.0.0.1")
PORT = int(os.environ.get("STOCK_CHART_PORT", "8002"))

WEB_DIR = Path(__file__).resolve().parent / "web"
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
WATCHGROUPS_PATH = PROJECT_ROOT / "data" / "watchgroups.json"
WATCHLIST_YAML = PROJECT_ROOT / "skills" / "report" / "watchlist.yaml"

# range → 거래일 수 (대략: 1개월 ≈ 21 거래일)
RANGE_LIMIT = {"3m": 66, "6m": 132, "1y": 264, "3y": 760, "all": 100000}


def _stock_name(code):
    rows = db._query("SELECT name FROM securities WHERE code=?", [code])
    return rows[0]["name"] if rows else code


def get_ohlcv(code, rng):
    """오름차순 OHLCV + 종목명. Lightweight Charts 포맷(time=YYYY-MM-DD)."""
    limit = RANGE_LIMIT.get(rng, RANGE_LIMIT["1y"])
    rows = db.get_daily_prices(code, limit=limit)  # DESC
    rows = list(reversed(rows))  # 차트는 오름차순 필요
    ohlcv = [
        {
            "time": r["date"],
            "open": r["open"],
            "high": r["high"],
            "low": r["low"],
            "close": r["close"],
            "volume": r["volume"],
        }
        for r in rows
    ]
    return {"code": code, "name": _stock_name(code), "ohlcv": ohlcv}


def search(q):
    """종목 검색 — 코드 또는 이름 부분일치 (상장 종목 우선)."""
    if not q:
        return []
    like = f"%{q}%"
    rows = db._query(
        """SELECT code, name, market FROM securities
           WHERE (name LIKE ? OR code LIKE ?) AND delisted_at IS NULL
           ORDER BY CASE WHEN code=? OR name=? THEN 0 ELSE 1 END, code
           LIMIT 10""",
        [like, like, q, q],
    )
    return rows


# ── 관심그룹 (즐겨찾기) ──────────────────────────────────

def _seed_groups_from_yaml():
    """watchlist.yaml 카테고리 → 초기 관심그룹. 실패 시 빈 목록."""
    try:
        import yaml
        d = yaml.safe_load(WATCHLIST_YAML.read_text(encoding="utf-8")) or {}
        return [
            {"name": name, "codes": [it["code"] for it in items]}
            for name, items in (d.get("categories") or {}).items()
        ]
    except Exception:
        return []


def _load_groups():
    if WATCHGROUPS_PATH.exists():
        return json.loads(WATCHGROUPS_PATH.read_text(encoding="utf-8")).get("groups", [])
    groups = _seed_groups_from_yaml()  # 최초 1회 시드
    _save_groups(groups)
    return groups


def _save_groups(groups):
    WATCHGROUPS_PATH.parent.mkdir(parents=True, exist_ok=True)
    WATCHGROUPS_PATH.write_text(
        json.dumps({"groups": groups}, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _quotes(codes):
    """여러 종목의 최신 시세(종가·등락률·전일대비) 한 번에 조회."""
    if not codes:
        return {}
    ph = ",".join("?" * len(codes))
    rows = db._query(
        f"""SELECT dp.code AS code, s.name AS name, dp.close AS close, dp.change_rate AS rate
            FROM daily_prices dp
            JOIN securities s ON s.code = dp.code
            JOIN (SELECT code, MAX(date) AS d FROM daily_prices WHERE code IN ({ph}) GROUP BY code) m
              ON m.code = dp.code AND m.d = dp.date""",
        list(codes),
    )
    out = {}
    for r in rows:
        close, rate = r["close"], r["rate"] or 0
        prev = close / (1 + rate / 100) if rate != -100 else close
        out[r["code"]] = {"code": r["code"], "name": r["name"], "close": close,
                          "change": round(close - prev), "change_rate": rate}
    return out


def groups_enriched():
    """그룹 + 각 종목 최신 시세."""
    groups = _load_groups()
    q = _quotes([c for g in groups for c in g["codes"]])
    return [
        {"name": g["name"],
         "stocks": [q.get(c, {"code": c, "name": c, "close": None, "change": 0, "change_rate": 0})
                    for c in g["codes"]]}
        for g in groups
    ]


def save_groups(body):
    """{groups:[{name, codes:[...]}]} 저장 (name/codes만 화이트리스트)."""
    clean = [{"name": str(g.get("name", "")).strip(),
              "codes": [str(c) for c in (g.get("codes") or [])]}
             for g in (body.get("groups") or [])]
    _save_groups(clean)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # 조용히

    def _json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path, ctype):
        try:
            data = path.read_bytes()
        except FileNotFoundError:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        try:
            if u.path == "/api/ohlcv":
                code = (q.get("code") or [""])[0].strip()
                rng = (q.get("range") or ["1y"])[0]
                if not code:
                    return self._json({"error": "code required"}, 400)
                return self._json(get_ohlcv(code, rng))
            if u.path == "/api/search":
                return self._json(search((q.get("q") or [""])[0].strip()))
            if u.path == "/api/groups":
                return self._json({"groups": groups_enriched()})
            if u.path in ("/", "/index.html"):
                return self._file(WEB_DIR / "index.html", "text/html; charset=utf-8")
            self.send_error(404)
        except Exception as e:
            self._json({"error": str(e)}, 500)

    def do_PUT(self):
        u = urlparse(self.path)
        try:
            if u.path == "/api/groups":
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length) or b"{}")
                save_groups(body)
                return self._json({"ok": True})
            self.send_error(404)
        except Exception as e:
            self._json({"error": str(e)}, 500)


def main():
    print(f"stock-chart MVP → http://{HOST}:{PORT}  (data: {db._REMOTE_HOST or 'local market.db'})")
    HTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()

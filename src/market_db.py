"""시장 데이터 DB — SQLite 기반 전 종목 시계열 저장.

테이블: securities, daily_prices, daily_valuations, investor_flow,
       financials, daily_screening, journal_trades
"""

import os
import sqlite3
from datetime import datetime

_DB_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DB_PATH = os.path.join(_DB_DIR, "market.db")

_conn = None


def _get_conn():
    global _conn
    if _conn is None:
        os.makedirs(_DB_DIR, exist_ok=True)
        _conn = sqlite3.connect(DB_PATH)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA foreign_keys=ON")
    return _conn


def init(db_path=None):
    """DB 스키마 생성."""
    global DB_PATH, _conn
    if db_path:
        DB_PATH = db_path
        _conn = None
    conn = _get_conn()
    conn.executescript(_SCHEMA)
    conn.commit()


# ── 스키마 ──────────────────────────────────────────────

_SCHEMA = """
-- 종목 마스터
CREATE TABLE IF NOT EXISTS securities (
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    market TEXT NOT NULL,            -- 'KOSPI' / 'KOSDAQ'
    sector TEXT,
    is_etp INTEGER DEFAULT 0,
    is_spac INTEGER DEFAULT 0,
    is_halt INTEGER DEFAULT 0,
    is_admin INTEGER DEFAULT 0,
    mktcap INTEGER,                  -- 억원 (마스터파일 기준)
    listed_at TEXT,
    delisted_at TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    PRIMARY KEY (code, market)
);

-- 일별 OHLCV + 시총
CREATE TABLE IF NOT EXISTS daily_prices (
    code TEXT NOT NULL,
    date TEXT NOT NULL,
    open INTEGER,
    high INTEGER,
    low INTEGER,
    close INTEGER NOT NULL,
    volume INTEGER,
    trade_value INTEGER,             -- 거래대금
    mktcap INTEGER,                  -- 억원
    change_rate REAL,
    PRIMARY KEY (code, date)
);

-- 일별 밸류에이션
CREATE TABLE IF NOT EXISTS daily_valuations (
    code TEXT NOT NULL,
    date TEXT NOT NULL,
    per REAL,
    pbr REAL,
    eps REAL,
    bps REAL,
    foreign_ratio REAL,              -- 외국인 보유비율 %
    PRIMARY KEY (code, date)
);

-- 일별 투자자 수급
CREATE TABLE IF NOT EXISTS investor_flow (
    code TEXT NOT NULL,
    date TEXT NOT NULL,
    foreign_net INTEGER,             -- 주수
    institution_net INTEGER,
    individual_net INTEGER,
    PRIMARY KEY (code, date)
);

-- 재무제표 (연간/분기)
CREATE TABLE IF NOT EXISTS financials (
    code TEXT NOT NULL,
    period TEXT NOT NULL,             -- 'YYYY' or 'YYYYQN'
    period_type TEXT NOT NULL,        -- 'annual' / 'quarterly'
    revenue INTEGER,                  -- 억원
    oper_profit INTEGER,
    net_profit INTEGER,
    roe REAL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    PRIMARY KEY (code, period)
);

-- 사전계산 스크리닝 지표
CREATE TABLE IF NOT EXISTS daily_screening (
    code TEXT NOT NULL,
    date TEXT NOT NULL,
    close INTEGER,
    mktcap INTEGER,
    per REAL,
    pbr REAL,
    ma5 REAL,
    ma20 REAL,
    ma60 REAL,
    ma120 REAL,
    return_1d REAL,
    return_5d REAL,
    return_20d REAL,
    return_60d REAL,
    volume_ratio_5d REAL,
    foreign_net_5d INTEGER,
    foreign_net_20d INTEGER,
    institution_net_5d INTEGER,
    foreign_ratio REAL,
    PRIMARY KEY (code, date)
);

-- 매매일지
CREATE TABLE IF NOT EXISTS journal_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    side TEXT NOT NULL,               -- 'buy' / 'sell' / 'cut'
    qty INTEGER NOT NULL,
    price INTEGER NOT NULL,
    total_amount INTEGER NOT NULL,
    traded_at TEXT NOT NULL,
    strategy TEXT,                    -- 'momentum' / 'value' / 'swing' / 'breakout'
    emotion TEXT,                     -- 'confident' / 'fomo' / 'fearful' / 'calm' / 'impulsive'
    reason TEXT,
    post_note TEXT,
    pnl INTEGER,
    pnl_rate REAL,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_prices_date ON daily_prices(date);
CREATE INDEX IF NOT EXISTS idx_valuations_date ON daily_valuations(date);
CREATE INDEX IF NOT EXISTS idx_flow_date ON investor_flow(date);
CREATE INDEX IF NOT EXISTS idx_screening_date ON daily_screening(date);
CREATE INDEX IF NOT EXISTS idx_screening_date_per ON daily_screening(date, per);
CREATE INDEX IF NOT EXISTS idx_screening_date_mktcap ON daily_screening(date, mktcap DESC);
CREATE INDEX IF NOT EXISTS idx_journal_code ON journal_trades(code);
CREATE INDEX IF NOT EXISTS idx_journal_date ON journal_trades(traded_at);
CREATE INDEX IF NOT EXISTS idx_securities_active ON securities(is_halt, is_admin);
"""


# ── Securities ──────────────────────────────────────────

def upsert_securities(rows):
    """종목 마스터 upsert. Returns: 건수."""
    conn = _get_conn()
    conn.executemany(
        """INSERT INTO securities (code, name, market, sector, is_etp, is_spac,
               is_halt, is_admin, mktcap, updated_at)
           VALUES (:code, :name, :market, :sector, :is_etp, :is_spac,
               :is_halt, :is_admin, :mktcap, datetime('now','localtime'))
           ON CONFLICT(code, market) DO UPDATE SET
               name=excluded.name, sector=excluded.sector,
               is_etp=excluded.is_etp, is_spac=excluded.is_spac,
               is_halt=excluded.is_halt, is_admin=excluded.is_admin,
               mktcap=excluded.mktcap,
               updated_at=datetime('now','localtime')""",
        rows,
    )
    conn.commit()
    return len(rows)


def get_active_codes(market=None):
    """활성 종목 코드 목록 (ETP/SPAC/관리/거래정지 제외)."""
    conn = _get_conn()
    sql = """SELECT code FROM securities
             WHERE is_etp=0 AND is_spac=0 AND is_halt=0 AND is_admin=0
               AND delisted_at IS NULL"""
    params = []
    if market:
        sql += " AND market=?"
        params.append(market)
    sql += " ORDER BY mktcap DESC"
    return [r["code"] for r in conn.execute(sql, params).fetchall()]


def get_all_codes(market=None):
    """전체 종목 코드 목록."""
    conn = _get_conn()
    sql = "SELECT code FROM securities WHERE delisted_at IS NULL"
    params = []
    if market:
        sql += " AND market=?"
        params.append(market)
    return [r["code"] for r in conn.execute(sql, params).fetchall()]


# ── Daily Prices ────────────────────────────────────────

def insert_daily_prices(rows):
    """일별 시세 bulk insert (중복 무시)."""
    conn = _get_conn()
    conn.executemany(
        """INSERT OR IGNORE INTO daily_prices
           (code, date, open, high, low, close, volume, trade_value, mktcap, change_rate)
           VALUES (:code, :date, :open, :high, :low, :close, :volume,
                   :trade_value, :mktcap, :change_rate)""",
        rows,
    )
    conn.commit()
    return len(rows)


def upsert_daily_prices(rows):
    """일별 시세 upsert (당일 데이터 갱신용)."""
    conn = _get_conn()
    conn.executemany(
        """INSERT INTO daily_prices
           (code, date, open, high, low, close, volume, trade_value, mktcap, change_rate)
           VALUES (:code, :date, :open, :high, :low, :close, :volume,
                   :trade_value, :mktcap, :change_rate)
           ON CONFLICT(code, date) DO UPDATE SET
               open=excluded.open, high=excluded.high, low=excluded.low,
               close=excluded.close, volume=excluded.volume,
               trade_value=excluded.trade_value, mktcap=excluded.mktcap,
               change_rate=excluded.change_rate""",
        rows,
    )
    conn.commit()
    return len(rows)


def get_daily_prices(code, start=None, end=None, limit=None):
    """종목 일별 시세 조회."""
    conn = _get_conn()
    sql = "SELECT * FROM daily_prices WHERE code=?"
    params = [code]
    if start:
        sql += " AND date>=?"
        params.append(start)
    if end:
        sql += " AND date<=?"
        params.append(end)
    sql += " ORDER BY date DESC"
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


# ── Daily Valuations ────────────────────────────────────

def upsert_daily_valuations(rows):
    """일별 밸류에이션 upsert."""
    conn = _get_conn()
    conn.executemany(
        """INSERT INTO daily_valuations (code, date, per, pbr, eps, bps, foreign_ratio)
           VALUES (:code, :date, :per, :pbr, :eps, :bps, :foreign_ratio)
           ON CONFLICT(code, date) DO UPDATE SET
               per=excluded.per, pbr=excluded.pbr, eps=excluded.eps,
               bps=excluded.bps, foreign_ratio=excluded.foreign_ratio""",
        rows,
    )
    conn.commit()
    return len(rows)


# ── Investor Flow ───────────────────────────────────────

def insert_investor_flow(rows):
    """투자자 수급 bulk insert (중복 무시)."""
    conn = _get_conn()
    conn.executemany(
        """INSERT OR IGNORE INTO investor_flow
           (code, date, foreign_net, institution_net, individual_net)
           VALUES (:code, :date, :foreign_net, :institution_net, :individual_net)""",
        rows,
    )
    conn.commit()
    return len(rows)


def get_investor_flow(code, start=None, end=None):
    """종목 투자자 수급 조회."""
    conn = _get_conn()
    sql = "SELECT * FROM investor_flow WHERE code=?"
    params = [code]
    if start:
        sql += " AND date>=?"
        params.append(start)
    if end:
        sql += " AND date<=?"
        params.append(end)
    sql += " ORDER BY date DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


# ── Financials ──────────────────────────────────────────

def upsert_financials(rows):
    """재무제표 upsert."""
    conn = _get_conn()
    conn.executemany(
        """INSERT INTO financials
           (code, period, period_type, revenue, oper_profit, net_profit, roe, updated_at)
           VALUES (:code, :period, :period_type, :revenue, :oper_profit,
                   :net_profit, :roe, datetime('now','localtime'))
           ON CONFLICT(code, period) DO UPDATE SET
               revenue=excluded.revenue, oper_profit=excluded.oper_profit,
               net_profit=excluded.net_profit, roe=excluded.roe,
               updated_at=datetime('now','localtime')""",
        rows,
    )
    conn.commit()
    return len(rows)


# ── Daily Screening ─────────────────────────────────────

def upsert_daily_screening(rows):
    """스크리닝 지표 upsert."""
    conn = _get_conn()
    conn.executemany(
        """INSERT INTO daily_screening
           (code, date, close, mktcap, per, pbr, ma5, ma20, ma60, ma120,
            return_1d, return_5d, return_20d, return_60d,
            volume_ratio_5d, foreign_net_5d, foreign_net_20d,
            institution_net_5d, foreign_ratio)
           VALUES (:code, :date, :close, :mktcap, :per, :pbr,
                   :ma5, :ma20, :ma60, :ma120,
                   :return_1d, :return_5d, :return_20d, :return_60d,
                   :volume_ratio_5d, :foreign_net_5d, :foreign_net_20d,
                   :institution_net_5d, :foreign_ratio)
           ON CONFLICT(code, date) DO UPDATE SET
               close=excluded.close, mktcap=excluded.mktcap,
               per=excluded.per, pbr=excluded.pbr,
               ma5=excluded.ma5, ma20=excluded.ma20,
               ma60=excluded.ma60, ma120=excluded.ma120,
               return_1d=excluded.return_1d, return_5d=excluded.return_5d,
               return_20d=excluded.return_20d, return_60d=excluded.return_60d,
               volume_ratio_5d=excluded.volume_ratio_5d,
               foreign_net_5d=excluded.foreign_net_5d,
               foreign_net_20d=excluded.foreign_net_20d,
               institution_net_5d=excluded.institution_net_5d,
               foreign_ratio=excluded.foreign_ratio""",
        rows,
    )
    conn.commit()
    return len(rows)


def get_screening(date, filters=None, sort_by="mktcap", ascending=False, limit=50):
    """스크리닝 결과 조회.

    filters: dict of {field: (op, value)} e.g. {"per": ("between", (3, 10))}
    """
    conn = _get_conn()
    sql = """SELECT ds.*, s.name, s.market, s.sector
             FROM daily_screening ds
             JOIN securities s ON s.code = ds.code
             WHERE ds.date = ?
               AND s.is_etp=0 AND s.is_spac=0 AND s.is_halt=0 AND s.is_admin=0"""
    params = [date]

    if filters:
        for field, (op, value) in filters.items():
            if op == "between":
                sql += f" AND ds.{field} BETWEEN ? AND ?"
                params.extend(value)
            elif op in (">=", "<=", ">", "<", "=", "!="):
                sql += f" AND ds.{field} {op} ?"
                params.append(value)

    order = "ASC" if ascending else "DESC"
    sql += f" ORDER BY ds.{sort_by} {order} LIMIT ?"
    params.append(limit)

    return [dict(r) for r in conn.execute(sql, params).fetchall()]


# ── Journal ─────────────────────────────────────────────

def add_trade(trade):
    """매매일지 기록 추가. Returns: id."""
    conn = _get_conn()
    cur = conn.execute(
        """INSERT INTO journal_trades
           (code, name, side, qty, price, total_amount, traded_at,
            strategy, emotion, reason, post_note, pnl, pnl_rate)
           VALUES (:code, :name, :side, :qty, :price, :total_amount, :traded_at,
                   :strategy, :emotion, :reason, :post_note, :pnl, :pnl_rate)""",
        {
            "code": trade["code"],
            "name": trade["name"],
            "side": trade["side"],
            "qty": trade["qty"],
            "price": trade["price"],
            "total_amount": trade.get("total_amount", trade["qty"] * trade["price"]),
            "traded_at": trade.get("traded_at", datetime.now().strftime("%Y-%m-%d")),
            "strategy": trade.get("strategy"),
            "emotion": trade.get("emotion"),
            "reason": trade.get("reason"),
            "post_note": trade.get("post_note"),
            "pnl": trade.get("pnl"),
            "pnl_rate": trade.get("pnl_rate"),
        },
    )
    conn.commit()
    return cur.lastrowid


def get_trades(code=None, start=None, end=None, limit=100):
    """매매일지 조회."""
    conn = _get_conn()
    sql = "SELECT * FROM journal_trades WHERE 1=1"
    params = []
    if code:
        sql += " AND code=?"
        params.append(code)
    if start:
        sql += " AND traded_at>=?"
        params.append(start)
    if end:
        sql += " AND traded_at<=?"
        params.append(end)
    sql += " ORDER BY traded_at DESC, id DESC LIMIT ?"
    params.append(limit)
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


# ── Utility ─────────────────────────────────────────────

def get_latest_date(table="daily_prices"):
    """테이블의 최신 날짜 조회."""
    conn = _get_conn()
    row = conn.execute(f"SELECT MAX(date) as d FROM {table}").fetchone()
    return row["d"] if row else None


def count(table):
    """테이블 행 수."""
    conn = _get_conn()
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

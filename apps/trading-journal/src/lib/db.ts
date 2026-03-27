import Database from "better-sqlite3";
import path from "path";

const DB_PATH = path.join(process.cwd(), "..", "..", "data", "market.db");

let _db: Database.Database | null = null;

function getDb(): Database.Database {
  if (!_db) {
    _db = new Database(DB_PATH, { readonly: true });
    _db.pragma("journal_mode = WAL");
  }
  return _db;
}

export interface Security {
  code: string;
  name: string;
  market: string;
  sector: string | null;
  mktcap: number;
}

export interface DailyPrice {
  code: string;
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  mktcap: number;
  change_rate: number;
}

export interface ScreeningRow {
  code: string;
  date: string;
  name: string;
  market: string;
  sector: string | null;
  close: number;
  mktcap: number;
  per: number | null;
  pbr: number | null;
  ma5: number | null;
  ma20: number | null;
  ma60: number | null;
  ma120: number | null;
  return_1d: number | null;
  return_5d: number | null;
  return_20d: number | null;
  volume_ratio_5d: number | null;
  foreign_net_5d: number | null;
  foreign_net_20d: number | null;
  institution_net_5d: number | null;
  foreign_ratio: number | null;
}

export interface JournalTrade {
  id: number;
  code: string;
  name: string;
  side: string;
  qty: number;
  price: number;
  total_amount: number;
  traded_at: string;
  strategy: string | null;
  emotion: string | null;
  reason: string | null;
  post_note: string | null;
  pnl: number | null;
  pnl_rate: number | null;
}

// ── Queries ──

export function getLatestDate(): string {
  const row = getDb()
    .prepare("SELECT MAX(date) as d FROM daily_screening")
    .get() as { d: string } | undefined;
  return row?.d ?? "";
}

export function getMarketOverview() {
  const date = getLatestDate();
  if (!date) return null;

  const db = getDb();

  const stats = db
    .prepare(
      `SELECT
        COUNT(*) as total,
        SUM(CASE WHEN change_rate > 0 THEN 1 ELSE 0 END) as advance,
        SUM(CASE WHEN change_rate < 0 THEN 1 ELSE 0 END) as decline,
        ROUND(AVG(change_rate), 2) as avg_change
      FROM daily_prices WHERE date = ?`
    )
    .get(date) as Record<string, number>;

  const topGainers = db
    .prepare(
      `SELECT p.code, s.name, p.close, p.change_rate, p.volume, p.mktcap
       FROM daily_prices p JOIN securities s ON s.code = p.code
       WHERE p.date = ? AND s.is_etp=0 AND s.is_spac=0
       ORDER BY p.change_rate DESC LIMIT 10`
    )
    .all(date);

  const topVolume = db
    .prepare(
      `SELECT p.code, s.name, p.close, p.change_rate, p.volume, p.mktcap
       FROM daily_prices p JOIN securities s ON s.code = p.code
       WHERE p.date = ? AND s.is_etp=0 AND s.is_spac=0
       ORDER BY p.volume DESC LIMIT 10`
    )
    .all(date);

  const foreignBuy = db
    .prepare(
      `SELECT ds.code, s.name, ds.close, ds.foreign_net_5d, ds.foreign_net_20d,
              ds.per, ds.mktcap, ds.foreign_ratio
       FROM daily_screening ds JOIN securities s ON s.code = ds.code
       WHERE ds.date = ? AND ds.foreign_net_5d > 0
         AND s.is_etp=0 AND s.is_spac=0 AND s.is_halt=0
       ORDER BY ds.foreign_net_5d DESC LIMIT 10`
    )
    .all(date);

  return { date, stats, topGainers, topVolume, foreignBuy };
}

export function getScreening(
  date: string,
  filters: Record<string, [string, number | number[]]> = {},
  sortBy = "mktcap",
  limit = 50
) {
  const db = getDb();
  let sql = `SELECT ds.*, s.name, s.market, s.sector
     FROM daily_screening ds
     JOIN securities s ON s.code = ds.code
     WHERE ds.date = ?
       AND s.is_etp=0 AND s.is_spac=0 AND s.is_halt=0 AND s.is_admin=0`;
  const params: (string | number)[] = [date];

  for (const [field, [op, value]] of Object.entries(filters)) {
    if (op === "between" && Array.isArray(value)) {
      sql += ` AND ds.${field} BETWEEN ? AND ?`;
      params.push(value[0], value[1]);
    } else {
      sql += ` AND ds.${field} ${op} ?`;
      params.push(value as number);
    }
  }

  sql += ` ORDER BY ds.${sortBy} DESC LIMIT ?`;
  params.push(limit);

  return db.prepare(sql).all(...params) as ScreeningRow[];
}

export function getStockDetail(code: string) {
  const db = getDb();

  const security = db
    .prepare("SELECT * FROM securities WHERE code = ?")
    .get(code) as Security | undefined;

  const prices = db
    .prepare(
      "SELECT * FROM daily_prices WHERE code = ? ORDER BY date DESC LIMIT 120"
    )
    .all(code) as DailyPrice[];

  const latestVal = db
    .prepare(
      "SELECT * FROM daily_valuations WHERE code = ? ORDER BY date DESC LIMIT 1"
    )
    .get(code);

  const flow = db
    .prepare(
      "SELECT * FROM investor_flow WHERE code = ? ORDER BY date DESC LIMIT 30"
    )
    .all(code);

  const screening = db
    .prepare(
      "SELECT * FROM daily_screening WHERE code = ? ORDER BY date DESC LIMIT 1"
    )
    .get(code);

  return { security, prices: prices.reverse(), latestVal, flow, screening };
}

export function getTrades(limit = 100) {
  return getDb()
    .prepare(
      "SELECT * FROM journal_trades ORDER BY traded_at DESC, id DESC LIMIT ?"
    )
    .all(limit) as JournalTrade[];
}

export function addTrade(trade: Omit<JournalTrade, "id">) {
  // Use a writable connection for inserts
  const writeDb = new Database(DB_PATH);
  writeDb.pragma("journal_mode = WAL");
  const stmt = writeDb.prepare(
    `INSERT INTO journal_trades
     (code, name, side, qty, price, total_amount, traded_at,
      strategy, emotion, reason, post_note, pnl, pnl_rate)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
  );
  const result = stmt.run(
    trade.code, trade.name, trade.side, trade.qty, trade.price,
    trade.total_amount, trade.traded_at,
    trade.strategy, trade.emotion, trade.reason, trade.post_note,
    trade.pnl, trade.pnl_rate
  );
  writeDb.close();
  return result.lastInsertRowid;
}

export function getTradeStats() {
  const db = getDb();
  const trades = db
    .prepare("SELECT * FROM journal_trades ORDER BY traded_at")
    .all() as JournalTrade[];

  if (trades.length === 0) return null;

  const sells = trades.filter((t) => t.side !== "buy" && t.pnl !== null);
  const wins = sells.filter((t) => (t.pnl ?? 0) > 0);

  const byEmotion: Record<string, { total: number; wins: number }> = {};
  for (const t of sells) {
    const em = t.emotion ?? "unknown";
    if (!byEmotion[em]) byEmotion[em] = { total: 0, wins: 0 };
    byEmotion[em].total++;
    if ((t.pnl ?? 0) > 0) byEmotion[em].wins++;
  }

  // 전략별 분석
  const byStrategy: Record<string, { total: number; wins: number; pnl: number }> = {};
  for (const t of sells) {
    const st = t.strategy ?? "unknown";
    if (!byStrategy[st]) byStrategy[st] = { total: 0, wins: 0, pnl: 0 };
    byStrategy[st].total++;
    byStrategy[st].pnl += t.pnl ?? 0;
    if ((t.pnl ?? 0) > 0) byStrategy[st].wins++;
  }

  // 월별 PnL
  const monthlyPnl: Record<string, number> = {};
  for (const t of sells) {
    const month = t.traded_at.slice(0, 7);
    monthlyPnl[month] = (monthlyPnl[month] ?? 0) + (t.pnl ?? 0);
  }

  // 종목별 성과
  const byStock: Record<string, { name: string; trades: number; pnl: number; wins: number }> = {};
  for (const t of sells) {
    if (!byStock[t.code]) byStock[t.code] = { name: t.name, trades: 0, pnl: 0, wins: 0 };
    byStock[t.code].trades++;
    byStock[t.code].pnl += t.pnl ?? 0;
    if ((t.pnl ?? 0) > 0) byStock[t.code].wins++;
  }

  // 감정별 평균 PnL
  const emotionPnl: Record<string, { total: number; wins: number; pnl: number; avgPnl: number }> = {};
  for (const t of sells) {
    const em = t.emotion ?? "unknown";
    if (!emotionPnl[em]) emotionPnl[em] = { total: 0, wins: 0, pnl: 0, avgPnl: 0 };
    emotionPnl[em].total++;
    emotionPnl[em].pnl += t.pnl ?? 0;
    if ((t.pnl ?? 0) > 0) emotionPnl[em].wins++;
  }
  for (const v of Object.values(emotionPnl)) {
    v.avgPnl = v.total > 0 ? Math.round(v.pnl / v.total) : 0;
  }

  return {
    totalTrades: trades.length,
    totalSells: sells.length,
    winRate: sells.length > 0 ? (wins.length / sells.length) * 100 : 0,
    totalPnl: sells.reduce((s, t) => s + (t.pnl ?? 0), 0),
    avgPnl: sells.length > 0 ? Math.round(sells.reduce((s, t) => s + (t.pnl ?? 0), 0) / sells.length) : 0,
    byEmotion,
    byStrategy,
    monthlyPnl,
    byStock,
    emotionPnl,
    allTrades: trades,
  };
}

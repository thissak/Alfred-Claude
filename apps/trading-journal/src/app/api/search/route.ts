import Database from "better-sqlite3";
import path from "path";
import { NextRequest, NextResponse } from "next/server";

const DB_PATH = path.join(process.cwd(), "..", "..", "data", "market.db");

export async function GET(req: NextRequest) {
  const q = req.nextUrl.searchParams.get("q") ?? "";
  if (q.length < 1) return NextResponse.json([]);

  const db = new Database(DB_PATH, { readonly: true });
  const results = db
    .prepare(
      `SELECT code, name, market, mktcap FROM securities
       WHERE (name LIKE ? OR code LIKE ?)
         AND delisted_at IS NULL
       ORDER BY mktcap DESC
       LIMIT 10`
    )
    .all(`%${q}%`, `%${q}%`);
  db.close();

  return NextResponse.json(results);
}

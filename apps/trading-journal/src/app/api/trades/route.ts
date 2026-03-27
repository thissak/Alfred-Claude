import { addTrade } from "@/lib/db";
import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  const body = await req.json();
  const id = addTrade(body);
  return NextResponse.json({ id });
}

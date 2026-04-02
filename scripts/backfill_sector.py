#!/usr/bin/env python3
"""securities 테이블 sector 백필 — KIS inquire-price API 사용."""
import sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import market_db as db
from kis_readonly_client import get as kis_get

db.init()
conn = db._get_conn()

# sector가 null인 종목만
rows = conn.execute(
    "SELECT code, name FROM securities WHERE sector IS NULL AND length(code) <= 6"
).fetchall()
print(f"sector 미입력 종목: {len(rows)}건")

updated = 0
errors = 0
for i, row in enumerate(rows):
    code = row["code"]
    try:
        resp = kis_get(
            "/uapi/domestic-stock/v1/quotations/inquire-price",
            "FHKST01010100",
            {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code},
        )
        output = resp.get("output", {}) if isinstance(resp, dict) else {}
        sector = output.get("bstp_kor_isnm")
        if sector:
            conn.execute(
                "UPDATE securities SET sector=? WHERE code=?", (sector, code)
            )
            conn.commit()
            updated += 1
    except Exception as e:
        errors += 1
        if errors <= 3:
            print(f"  ERROR {code}: {e}")

    if (i + 1) % 100 == 0:
        print(f"  {i+1}/{len(rows)} 처리 (업데이트 {updated}, 에러 {errors})")
    
    time.sleep(0.05)  # 초당 20건 제한

print(f"\n완료: {updated}건 업데이트, {errors}건 에러")

"""장중 급등/급락 모니터 — 등락률순위 폴링 → 뉴스 수집 → Claude 분석 → iMessage 발송.

평일 09:00~15:30, 5분 간격으로 등락률순위 API를 폴링.
신규 급등(+5%)/급락(-5%) 감지 시 뉴스 조회 후 claude -p로 분석, outbox에 드롭.
"""

import os
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
os.environ.setdefault("KIS_THROTTLE", "0.5")
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from scan_surge import _fetch_fluctuation_rank, fetch_news, _pick_best_news
from monitor_base import MonitorBase

MIN_RETURN = float(os.environ.get("INTRADAY_MIN_RETURN", "5.0"))


class IntradayMonitor(MonitorBase):
    name = "intraday"
    interval = 300
    weekday_only = True
    time_gate = (900, 1530)
    claude_model = "sonnet"
    claude_system_prompt = "장중 급등/급락 종목 분석가. 각 종목의 움직임을 뉴스 근거로 1~2문장 팩트 분석. 투자 의견 빼고 간결하게."

    def on_start(self):
        self.seen = set()
        self._date = ""
        self.log(f"임계값: ±{MIN_RETURN}%")

    def check(self):
        today = datetime.now().strftime("%Y-%m-%d")
        if today != self._date:
            self.seen.clear()
            self._date = today

        alerts = self._collect_alerts()
        if not alerts:
            return f"대기 ({len(self.seen)} seen)"

        up = [a for a in alerts if a["return_1d"] > 0]
        down = [a for a in alerts if a["return_1d"] < 0]
        self.log(f"신규: 급등 {len(up)}, 급락 {len(down)}")

        prompt = self._build_prompt(alerts, today)
        analysis = self.ask_claude(prompt)
        if analysis:
            text = analysis if isinstance(analysis, str) else str(analysis)
            self.write_outbox(text)
        return f"{len(alerts)}건"

    # ── private ───────────────────────────────────────

    def _collect_alerts(self):
        surges = _fetch_fluctuation_rank(MIN_RETURN)
        drops = _fetch_fluctuation_rank_drop(MIN_RETURN)

        new = []
        for s in surges + drops:
            key = (s["code"], self._date)
            if key in self.seen:
                continue
            news_list = fetch_news(s["code"])
            best = _pick_best_news(news_list)
            s["news_title"] = best["title"] if best else "-"
            new.append(s)
            self.seen.add(key)
        return new

    def _build_prompt(self, alerts, date_str):
        lines = []
        for i, a in enumerate(alerts, 1):
            sign = "+" if a["return_1d"] > 0 else ""
            lines.append(f"{i}. {a['name']} ({a['code']}) {sign}{a['return_1d']}%")
            lines.append(f"   뉴스: {a['news_title']}")

        return f"""아래는 {date_str} 장중 급등/급락 종목이야.
각 종목이 왜 움직였는지 뉴스 근거로 1~2문장 분석해줘.
투자 의견 빼고 팩트만. iMessage로 보낼거라 간결하게.

{chr(10).join(lines)}"""


def _fetch_fluctuation_rank_drop(min_drop=5.0):
    """등락률순위 (하락) 조회."""
    from kis_readonly_client import get as kis_get
    data = kis_get(
        "/uapi/domestic-stock/v1/ranking/fluctuation",
        "FHPST01700000",
        {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_COND_SCR_DIV_CODE": "20170",
            "FID_INPUT_ISCD": "0000",
            "FID_RANK_SORT_CLS_CODE": "1",
            "FID_INPUT_CNT_1": "0",
            "FID_PRC_CLS_CODE": "1",
            "FID_INPUT_PRICE_1": "",
            "FID_INPUT_PRICE_2": "",
            "FID_VOL_CNT": "",
            "FID_TRGT_CLS_CODE": "0",
            "FID_TRGT_EXLS_CLS_CODE": "0",
            "FID_DIV_CLS_CODE": "0",
            "FID_RSFL_RATE1": "",
            "FID_RSFL_RATE2": str(-min_drop),
        },
    )
    if not data:
        return []

    results = []
    for item in data.get("output", []):
        code = item.get("mksc_shrn_iscd") or item.get("stck_shrn_iscd", "")
        name = item.get("hts_kor_isnm", "")
        rate = item.get("prdy_ctrt", "0")
        vol = item.get("acml_vol", "0")
        if not code:
            continue
        try:
            rate_f = float(rate)
        except ValueError:
            continue
        if rate_f > -min_drop:
            continue
        results.append({
            "code": code,
            "name": name,
            "return_1d": round(rate_f, 2),
            "volume": int(vol) if vol else 0,
        })
    return results


if __name__ == "__main__":
    IntradayMonitor().run()

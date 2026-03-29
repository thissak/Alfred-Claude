"""종목 일봉 캔들차트 + 이상패턴 마킹."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import mplfinance as mpf
import pandas as pd
from datetime import datetime

_USE_MARKET_DB = bool(os.environ.get("MARKET_DB_HOST"))

if _USE_MARKET_DB:
    from src.market_db import _query
else:
    from src.kis_readonly_client import get

# 한글 폰트
font_path = "/System/Library/Fonts/AppleSDGothicNeo.ttc"
fm.fontManager.addfont(font_path)
plt.rcParams["font.family"] = "Apple SD Gothic Neo"
plt.rcParams["axes.unicode_minus"] = False


def fetch_candles(code: str, days: int = 90) -> pd.DataFrame:
    from datetime import timedelta

    if _USE_MARKET_DB:
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        db_rows = _query(
            "SELECT date, open, high, low, close, volume FROM daily_prices "
            "WHERE code=? AND date>=? ORDER BY date",
            [code, start],
        )
        if not db_rows:
            return pd.DataFrame()
        rows = []
        for r in db_rows:
            rows.append({
                "Date": pd.Timestamp(r["date"]),
                "Open": int(r["open"]),
                "High": int(r["high"]),
                "Low": int(r["low"]),
                "Close": int(r["close"]),
                "Volume": int(r["volume"]),
            })
        return pd.DataFrame(rows).set_index("Date").sort_index()

    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
    res = get(
        "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice",
        "FHKST03010100",
        {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": code,
            "FID_INPUT_DATE_1": start,
            "FID_INPUT_DATE_2": end,
            "FID_PERIOD_DIV_CODE": "D",
            "FID_ORG_ADJ_PRC": "0",
        },
    )
    if not res:
        return pd.DataFrame()

    rows = []
    for item in res.get("output2", []):
        try:
            rows.append({
                "Date": pd.Timestamp(datetime.strptime(item["stck_bsop_date"], "%Y%m%d")),
                "Open": int(item["stck_oprc"]),
                "High": int(item["stck_hgpr"]),
                "Low": int(item["stck_lwpr"]),
                "Close": int(item["stck_clpr"]),
                "Volume": int(item["acml_vol"]),
            })
        except (KeyError, ValueError):
            continue

    df = pd.DataFrame(rows).set_index("Date").sort_index()
    return df


def detect_events(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    """급등/급락 날짜 리스트 반환."""
    surge_dates = []
    drop_dates = []

    closes = df["Close"].values
    for i in range(1, len(closes)):
        if closes[i - 1] == 0:
            continue
        pct = (closes[i] - closes[i - 1]) / closes[i - 1] * 100
        dt = df.index[i].strftime("%Y-%m-%d")
        if pct >= 5:
            surge_dates.append(dt)
        elif pct <= -5:
            drop_dates.append(dt)

    return surge_dates, drop_dates


def generate_chart(code: str, name: str = "") -> str:
    df = fetch_candles(code)
    if df.empty:
        print("데이터 없음")
        return ""

    surge_dates, drop_dates = detect_events(df)

    # 마커 생성
    markers_up = []
    markers_dn = []
    for idx in df.index:
        ds = idx.strftime("%Y-%m-%d")
        if ds in surge_dates:
            markers_up.append(df.loc[idx, "High"] * 1.03)
            markers_dn.append(float("nan"))
        elif ds in drop_dates:
            markers_up.append(float("nan"))
            markers_dn.append(df.loc[idx, "Low"] * 0.97)
        else:
            markers_up.append(float("nan"))
            markers_dn.append(float("nan"))

    addplots = [
        mpf.make_addplot(pd.Series(markers_up, index=df.index), type="scatter", marker="^", markersize=100, color="#FF3333"),
        mpf.make_addplot(pd.Series(markers_dn, index=df.index), type="scatter", marker="v", markersize=100, color="#3333FF"),
    ]

    mc = mpf.make_marketcolors(up="#FF3333", down="#3366FF", edge="inherit", wick="inherit", volume="in")
    style = mpf.make_mpf_style(
        marketcolors=mc, gridstyle="-", gridcolor="#eeeeee",
        rc={"font.family": "Apple SD Gothic Neo"},
    )

    title = f"\n{name} ({code}) 일봉 차트  |  ▲급등 ▼급락" if name else f"\n{code} 일봉 차트"

    fig, axes = mpf.plot(
        df, type="candle", volume=True, style=style,
        title=title, ylabel="가격 (원)", ylabel_lower="거래량",
        figsize=(16, 9), addplot=addplots, returnfig=True,
    )

    # 주석 추가 (최근 5개 이벤트만)
    ax = axes[0]
    all_events = [(d, "surge") for d in surge_dates] + [(d, "drop") for d in drop_dates]
    all_events.sort()
    recent = all_events[-7:]  # 최근 7개

    for date_str, etype in recent:
        dt = pd.Timestamp(date_str)
        if dt not in df.index:
            continue
        idx_pos = list(df.index).index(dt)
        row = df.loc[dt]
        pct = 0
        if idx_pos > 0:
            prev_close = df.iloc[idx_pos - 1]["Close"]
            if prev_close > 0:
                pct = (row["Close"] - prev_close) / prev_close * 100

        if etype == "surge":
            price = row["High"]
            offset = price * 0.05
            color = "#FF3333"
        else:
            price = row["Low"]
            offset = -price * 0.05
            color = "#3333FF"

        label = f"{pct:+.1f}%"
        ax.annotate(
            label, xy=(idx_pos, price), xytext=(idx_pos, price + offset),
            fontsize=8, ha="center", color=color, fontweight="bold",
            arrowprops=dict(arrowstyle="->", color=color, lw=0.8),
        )

    outdir = Path("data/stock-analysis")
    outdir.mkdir(parents=True, exist_ok=True)
    outpath = str(outdir / f"{code}_chart.png")
    fig.savefig(outpath, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"차트 저장: {outpath}")
    return outpath


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python stock_surge_chart.py <종목코드> [종목명]")
        sys.exit(1)

    code = sys.argv[1]
    name = sys.argv[2] if len(sys.argv) > 2 else ""
    generate_chart(code, name)

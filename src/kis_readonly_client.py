"""Readonly KIS client for quote, balance, fill, and analysis APIs."""

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

APP_KEY = os.getenv("KIS_READONLY_APP_KEY")
APP_SECRET = os.getenv("KIS_READONLY_APP_SECRET")
ACCOUNT = os.getenv("KIS_READONLY_ACCOUNT")
BASE_URL = "https://openapi.koreainvestment.com:9443"
TOKEN_PATH = ROOT / "run" / "kis_token.json"

READONLY_ENDPOINTS = {
    (
        "/uapi/domestic-stock/v1/quotations/inquire-index-price",
        "FHPUP02100000",
    ),
    (
        "/uapi/domestic-stock/v1/trading/inquire-balance",
        "TTTC8434R",
    ),
    (
        "/uapi/domestic-stock/v1/trading/inquire-daily-ccld",
        "TTTC8001R",
    ),
    (
        "/uapi/domestic-stock/v1/ranking/fluctuation",
        "FHPST01700000",
    ),
    (
        "/uapi/domestic-stock/v1/quotations/volume-rank",
        "FHPST01710000",
    ),
    (
        "/uapi/domestic-stock/v1/quotations/inquire-price",
        "FHKST01010100",
    ),
    (
        "/uapi/overseas-price/v1/quotations/price",
        "HHDFS00000300",
    ),
    (
        "/uapi/overseas-stock/v1/trading/inquire-balance",
        "TTTS3012R",
    ),
    (
        "/uapi/domestic-stock/v1/quotations/foreign-institution-total",
        "FHPTJ04400000",
    ),
    (
        "/uapi/domestic-stock/v1/finance/income-statement",
        "FHKST66430200",
    ),
}


def _require_env(name, value):
    if not value:
        raise RuntimeError(f"missing KIS credential: {name}")
    return value


def get_account():
    return _require_env("KIS_READONLY_ACCOUNT", ACCOUNT)


def _get_token():
    """Return cached token or issue a new one."""
    _require_env("KIS_READONLY_APP_KEY", APP_KEY)
    _require_env("KIS_READONLY_APP_SECRET", APP_SECRET)

    if TOKEN_PATH.exists():
        cached = json.loads(TOKEN_PATH.read_text())
        expires = datetime.fromisoformat(cached["expires_at"])
        if datetime.now() < expires - timedelta(minutes=10):
            return cached["access_token"]

    res = requests.post(
        f"{BASE_URL}/oauth2/tokenP",
        json={
            "grant_type": "client_credentials",
            "appkey": APP_KEY,
            "appsecret": APP_SECRET,
        },
    )
    data = res.json()
    if "access_token" not in data:
        raise RuntimeError(f"토큰 발급 실패: {data}")

    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(
        json.dumps(
            {
                "access_token": data["access_token"],
                "expires_at": (datetime.now() + timedelta(hours=23)).isoformat(),
            }
        )
    )
    return data["access_token"]


def _headers(tr_id):
    return {
        "authorization": f"Bearer {_get_token()}",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET,
        "tr_id": tr_id,
        "Content-Type": "application/json; charset=utf-8",
    }


def get(path, tr_id, params):
    """Readonly GET with endpoint allowlist enforcement."""
    if (path, tr_id) not in READONLY_ENDPOINTS:
        raise RuntimeError(
            f"KIS readonly guard blocked endpoint: path={path} tr_id={tr_id}"
        )

    res = requests.get(f"{BASE_URL}{path}", headers=_headers(tr_id), params=params)
    time.sleep(0.5)
    data = res.json()
    if data.get("rt_cd") != "0":
        print(f"  [WARN] {tr_id}: {data.get('msg1', 'unknown error')}")
        return None
    return data

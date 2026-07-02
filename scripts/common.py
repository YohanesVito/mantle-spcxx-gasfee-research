"""Shared helpers for Mantle SPCXx research scripts."""
import json
import time
import requests

MANTLE_RPC = "https://rpc.mantle.xyz"
POOL = "0xd14B0DcD319551AE4D7B12787c00EE1C1f9E1d2E"  # SPCXx/USDT0, Merchant Moe
HEADERS = {"Content-Type": "application/json"}

_id = 0


def rpc(method, params, url=MANTLE_RPC, retries=4):
    """Single JSON-RPC call with basic retry/backoff."""
    global _id
    _id += 1
    payload = {"jsonrpc": "2.0", "id": _id, "method": method, "params": params}
    last = None
    for attempt in range(retries):
        try:
            r = requests.post(url, json=payload, headers=HEADERS, timeout=40)
            j = r.json()
            if "error" in j:
                last = j["error"]
                # range/ratelimit errors -> backoff and retry
                time.sleep(0.4 * (attempt + 1))
                continue
            return j["result"]
        except Exception as e:  # noqa
            last = str(e)
            time.sleep(0.5 * (attempt + 1))
    raise RuntimeError(f"RPC {method} failed: {last}")


def to_int(hexstr):
    return int(hexstr, 16) if isinstance(hexstr, str) else hexstr


def eth_call(to, data, url=MANTLE_RPC):
    return rpc("eth_call", [{"to": to, "data": data}, "latest"], url)


def erc20_decimals(token):
    # decimals() = 0x313ce567
    return to_int(eth_call(token, "0x313ce567"))


def erc20_symbol(token):
    # symbol() = 0x95d89b41
    raw = eth_call(token, "0x95d89b41")
    return _decode_string(raw)


def _decode_string(raw):
    b = bytes.fromhex(raw[2:])
    if len(b) == 32:  # bytes32 packed symbol
        return b.rstrip(b"\x00").decode("utf-8", "replace")
    # ABI-encoded string: offset(32) len(32) data
    if len(b) >= 64:
        length = int.from_bytes(b[32:64], "big")
        return b[64:64 + length].decode("utf-8", "replace")
    return raw


def block_timestamp(num):
    b = rpc("eth_getBlockByNumber", [hex(num), False])
    return to_int(b["timestamp"])


def latest_block():
    return to_int(rpc("eth_blockNumber", []))


# ---- SPCX Nasdaq baseline (cached; yfinance is intermittently flaky) ----
import os
SPCX_CACHE = os.path.join(os.path.dirname(__file__), "..", "data", "spcx_nasdaq.csv")
SPCX_CACHE_H = os.path.join(os.path.dirname(__file__), "..", "data", "spcx_nasdaq_hourly.csv")


def fetch_and_cache_spcx():
    """Best-effort: pull SPCX daily closes via yfinance and merge into cache.
    Returns the cached DataFrame (date, close) or None."""
    import pandas as pd
    try:
        import yfinance as yf
        h = yf.Ticker("SPCX").history(start="2026-06-12", interval="1d")
        if not h.empty:
            df = h[["Close"]].reset_index()
            df["date"] = pd.to_datetime(df["Date"]).dt.date.astype(str)
            df = df[["date", "Close"]].rename(columns={"Close": "close"})
            if os.path.exists(SPCX_CACHE):
                old = pd.read_csv(SPCX_CACHE)
                df = pd.concat([old, df]).drop_duplicates("date", keep="last")
            df.sort_values("date").to_csv(SPCX_CACHE, index=False)
    except Exception:
        pass
    if os.path.exists(SPCX_CACHE):
        import pandas as pd
        return pd.read_csv(SPCX_CACHE)
    return None


def fetch_and_cache_spcx_hourly():
    """Best-effort: pull SPCX hourly closes (market hours only) -> cache as UTC.
    Returns DataFrame (hour_utc, close) or None. Used for RQ1 overlap-hours alignment."""
    import pandas as pd
    try:
        import yfinance as yf
        h = yf.Ticker("SPCX").history(start="2026-06-12", interval="1h")
        if not h.empty:
            idx = h.index
            idx = idx.tz_convert("UTC") if idx.tz is not None else idx.tz_localize("UTC")
            df = pd.DataFrame({"hour_utc": idx.floor("h").astype(str),
                               "close": h["Close"].values})
            df = df.drop_duplicates("hour_utc", keep="last")
            if os.path.exists(SPCX_CACHE_H):
                old = pd.read_csv(SPCX_CACHE_H)
                df = pd.concat([old, df]).drop_duplicates("hour_utc", keep="last")
            df.sort_values("hour_utc").to_csv(SPCX_CACHE_H, index=False)
    except Exception:
        pass
    if os.path.exists(SPCX_CACHE_H):
        import pandas as pd
        return pd.read_csv(SPCX_CACHE_H)
    return None


def load_spcx():
    """Read cached SPCX daily (date, close); try a live refresh first. Never raises."""
    return fetch_and_cache_spcx()


def load_spcx_hourly():
    """Read cached SPCX hourly (hour_utc, close), market hours only. Never raises."""
    return fetch_and_cache_spcx_hourly()

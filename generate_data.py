import requests, json, os
from datetime import datetime

# Proxy configuration – use the SOCKS5 proxy (Clash Verge) reachable via Windows host IP
PROXY_PORT = 7898  # SOCKS5 proxy port
PROXY_HOST = "10.255.255.254"  # Windows host IP (LAN enabled)
PROXY_URL = f"socks5://{PROXY_HOST}:{PROXY_PORT}"

def get_okx_data():
    """Fetch all OKX USDT spot tickers. Tries via SOCKS5 proxy first, then direct request if needed."""
    url = "https://www.okx.com/api/v5/market/tickers?instType=SPOT"
    proxies = {"http": PROXY_URL, "https": PROXY_URL}
    try:
        resp = requests.get(url, timeout=15, proxies=proxies)
        resp.raise_for_status()
        result = resp.json()
        if result.get("code") != "0":
            print(f"API error (proxy) code: {result.get('code')}")
            return []
        return [t for t in result["data"] if t["instId"].endswith("USDT")]
    except Exception as e:
        print(f"Proxy request failed ({e}), retrying without proxy...")
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            result = resp.json()
            if result.get("code") != "0":
                print(f"API error (direct) code: {result.get('code')}")
                return []
            return [t for t in result["data"] if t["instId"].endswith("USDT")]
        except Exception as e2:
            print(f"Direct request also failed: {e2}")
            return []

def get_change(t):
    """Return 24h change percentage. Compute from open24h/last (OKX v5 doesn't include change24h)."""
    try:
        last = float(t.get('last', 0))
        open24 = float(t.get('open24h', 0))
        if open24 == 0:
            # fallback to sodUtc8 (UTC+8 mid-night open)
            sod = t.get('sodUtc8')
            if sod:
                sod_f = float(sod)
                if sod_f != 0:
                    return (last - sod_f) / sod_f * 100
            return 0.0
        return (last - open24) / open24 * 100
    except Exception:
        return 0.0

def volatility_rate(t):
    try:
        high = float(t.get('high24h', 0))
        low = float(t.get('low24h', 0))
        if low == 0:
            return None
        return (high - low) / low * 100
    except Exception:
        return None

def format_change(val):
    sign = '+' if val >= 0 else '-'
    return f"{sign}{abs(val):.2f}%"

def analyze(data):
    # Short‑term volatile: sort all pairs by absolute change descending
    short_term = []
    for t in data:
        change = get_change(t)
        short_term.append({
            "pair": t["instId"],
            "price": f"{float(t.get('last',0)):.4f}",
            "change": format_change(change),
            "volume": f"{int(float(t.get('volCcy24h',0))):,}"
        })
    short_term.sort(key=lambda x: abs(float(x['change'].replace('%',''))), reverse=True)

    # Flat‑start: volatility <5% and reasonable volume
    flat_start = []
    for t in data:
        vol = float(t.get('volCcy24h', 0))
        vr = volatility_rate(t)
        if vr is not None and vr < 5 and (vol > 5e6 or (float(t.get('high24h',0)) - float(t.get('last',0))) / float(t.get('high24h',0)) < 0.01):
            change = get_change(t)
            flat_start.append({
                "pair": t["instId"],
                "price": f"{float(t.get('last',0)):.4f}",
                "change": format_change(change),
                "volume": f"{int(vol):,}",
                "volatility": f"{vr:.2f}%"
            })

    # Top volume: all pairs sorted by volume descending
    top_volume = sorted(data, key=lambda x: float(x.get('volCcy24h', 0)), reverse=True)
    top_volume = [{
        "pair": t["instId"],
        "price": f"{float(t.get('last',0)):.4f}",
        "change": format_change(get_change(t)),
        "volume": f"{int(float(t.get('volCcy24h',0))):,}"
    } for t in top_volume]

    # Top gainers: positive change sorted descending
    gainers = sorted([t for t in data if get_change(t) > 0], key=lambda x: get_change(x), reverse=True)
    top_gainers = [{
        "pair": t["instId"],
        "price": f"{float(t.get('last',0)):.4f}",
        "change": format_change(get_change(t)),
        "volume": f"{int(float(t.get('volCcy24h',0))):,}"
    } for t in gainers]

    # Top losers: negative change sorted ascending
    losers = sorted([t for t in data if get_change(t) < 0], key=lambda x: get_change(x))
    top_losers = [{
        "pair": t["instId"],
        "price": f"{float(t.get('last',0)):.4f}",
        "change": format_change(get_change(t)),
        "volume": f"{int(float(t.get('volCcy24h',0))):,}"
    } for t in losers]

    return {
        "short_term": short_term,
        "flat_start": flat_start,
        "top_volume": top_volume,
        "top_gainers": top_gainers,
        "top_losers": top_losers
    }

def main():
    data = get_okx_data()
    if not data:
        print("No data fetched, aborting.")
        return
    result = analyze(data)
    out_path = os.path.join(os.path.expanduser("~"), "signal-crypto", "data.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"Data written to {out_path}")

if __name__ == "__main__":
    main()

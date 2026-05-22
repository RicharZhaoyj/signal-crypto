import requests
import json
from datetime import datetime

def fetch_okx_data():
    url = "https://www.okx.com/api/v5/market/tickers?instType=SPOT"
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") == "0":
            return [t for t in data["data"] if t["instId"].endswith("-USDT")]
    except Exception as e:
        print(f"Error fetching OKX data: {e}")
    return []

def analyze_data(tickers):
    volatile = []
    sideways = []
    top_volume = []
    up_count = 0
    down_count = 0
    total_volume = 0
    btc = None
    eth = None

    for t in tickers:
        try:
            last = float(t.get("last", 0))
            open24 = float(t.get("open24h", 0))
            high = float(t.get("high24h", 0))
            low = float(t.get("low24h", 0))
            vol = float(t.get("volCcy24h", 0))

            change = ((last - open24) / open24 * 100) if open24 > 0 else 0
            volatility = ((high - low) / low * 100) if low > 0 else 0

            total_volume += vol

            item = {
                "symbol": t["instId"],
                "price": last,
                "change": round(change, 2),
                "volume": vol
            }

            if t["instId"] == "BTC-USDT":
                btc = {"price": last, "change24h": round(change, 2), "volume": vol}
            if t["instId"] == "ETH-USDT":
                eth = {"price": last, "change24h": round(change, 2), "volume": vol}

            if abs(change) >= 5:
                volatile.append(item)

            if volatility < 5 and vol > 500000 and not any(x in t["instId"] for x in ["USD", "USDT"]):
                sideways.append({**item, "volatility": round(volatility, 2)})

            top_volume.append(item)

            if change > 0:
                up_count += 1
            elif change < 0:
                down_count += 1

        except:
            continue

    volatile.sort(key=lambda x: abs(x["change"]), reverse=True)
    sideways.sort(key=lambda x: x.get("volatility", 999))
    top_volume.sort(key=lambda x: x["volume"], reverse=True)

    return {
        "timestamp": datetime.now().isoformat(),
        "totalPairs": len(tickers),
        "upCount": up_count,
        "downCount": down_count,
        "totalVolume": total_volume,
        "sentiment": "bullish" if up_count > down_count * 1.3 else "bearish" if down_count > up_count * 1.3 else "neutral",
        "btc": btc,
        "eth": eth,
        "volatile": volatile[:20],
        "sideways": sideways[:15],
        "topVolume": top_volume[:10]
    }

def main():
    print("Fetching OKX data...")
    tickers = fetch_okx_data()
    if not tickers:
        print("No data fetched")
        return

    print(f"Analyzing {len(tickers)} pairs...")
    market_data = analyze_data(tickers)

    # 保存 data.json
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(market_data, f, ensure_ascii=False, indent=2)

    print("data.json generated successfully")

    # 同时更新 index.html 的更新时间（简单替换）
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            html = f.read()

        now_str = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
        html = html.replace(
            'update-time">⏰ 2026/5/19 14:39:24</div>',
            f'update-time">⏰ {now_str}</div>'
        )

        with open("index.html", "w", encoding="utf-8") as f:
            f.write(html)

        print("index.html timestamp updated")
    except Exception as e:
        print(f"Could not update index.html timestamp: {e}")

    print("Done!")

if __name__ == "__main__":
    main()
import requests
import json
from datetime import datetime

def fetch_okx_data():
    url = "https://www.okx.com/api/v5/market/tickers?instType=SPOT"
    try:
        resp = requests.get(url, timeout=20)
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
            volatility = ((high - low) / low * 100) if low > 0 else 999

            total_volume += vol

            item = {
                "symbol": t["instId"],
                "price": round(last, 6),
                "change": round(change, 2),
                "volume": vol
            }

            if t["instId"] == "BTC-USDT":
                btc = {"price": last, "change24h": round(change, 2), "volume": vol}
            if t["instId"] == "ETH-USDT":
                eth = {"price": last, "change24h": round(change, 2), "volume": vol}

            # 异动品种
            if abs(change) >= 5:
                volatile.append(item)

            # ========== 长期横盘蓄势品种（进一步放宽） ==========
            is_stable = any(x in t["instId"] for x in ["USDC", "USDT", "BUSD", "DAI", "TUSD", "FDUSD"])
            
            price_position = (last - low) / (high - low) if high > low else 0.5
            
            # 放宽后的条件（当前市场横盘品种较少，进一步宽松）
            if (volatility < 8.0 and 
                vol > 500_000 and 
                not is_stable and
                price_position < 0.7 and
                -6.0 <= change <= 6.0):
                
                sideways.append({
                    **item,
                    "volatility": round(volatility, 2),
                    "position": round(price_position * 100, 1)
                })

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

    print(f"横盘蓄势品种数量: {len(sideways)}")
    print(f"异动品种数量: {len(volatile)}")

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
    print("开始拉取 OKX 数据...")
    tickers = fetch_okx_data()
    print(f"获取到 {len(tickers)} 个交易对")

    if not tickers:
        print("未获取到数据，退出")
        return

    market_data = analyze_data(tickers)

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(market_data, f, ensure_ascii=False, indent=2)

    print("data.json 生成成功")

if __name__ == "__main__":
    main()
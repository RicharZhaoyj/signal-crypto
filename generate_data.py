import requests
import json
from datetime import datetime
import time

STABLECOINS = ["USDC", "BUSD", "DAI", "TUSD", "FDUSD", "USDD", "GUSD", "USDP"]

def fetch_okx_data():
    url = "https://www.okx.com/api/v5/market/tickers?instType=SPOT"
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        print(f"Error fetching OKX data: {e}")
        return []
    data = resp.json()
    if data.get("code") == "0":
        return [t for t in data["data"] if t["instId"].endswith("-USDT")]
    return []

def fetch_7d_range(symbol):
    """拉取近7天日线，计算7d波动率和价格位置"""
    url = f"https://www.okx.com/api/v5/market/candles?instId={symbol}&bar=1D&limit=7"
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != "0" or not data.get("data"):
            return None
        candles = data["data"]
        highs = [float(c[2]) for c in candles]
        lows = [float(c[3]) for c in candles]
        closes = [float(c[4]) for c in candles]
        
        high_7d = max(highs)
        low_7d = min(lows)
        last_price = closes[0]
        
        if high_7d == low_7d:
            return {"vola_7d": 0, "position_7d": 0.5}
        
        vola_7d = (high_7d - low_7d) / low_7d * 100
        position_7d = (last_price - low_7d) / (high_7d - low_7d)
        return {"vola_7d": round(vola_7d, 2), "position_7d": round(position_7d, 3)}
    except Exception as e:
        return None

def analyze_data(tickers):
    volatile = []
    sideways = []
    top_volume = []
    up_count = 0
    down_count = 0
    total_volume = 0
    btc = None
    eth = None

    candidates = []

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

            if abs(change) >= 5:
                volatile.append(item)

            # 第一阶段：排除稳定币交易对
            base = t["instId"].split("-")[0]
            is_stable = base in STABLECOINS
            if not is_stable:
                candidates.append(item)

            top_volume.append(item)

            if change > 0:
                up_count += 1
            elif change < 0:
                down_count += 1

        except:
            continue

    print(f"第一阶段候选币种: {len(candidates)} 个，开始拉取7d历史数据...")

    # 第二阶段：7d数据做核心判断
    for item in candidates[:90]:
        symbol = item["symbol"]
        hist = fetch_7d_range(symbol)
        time.sleep(0.11)

        if not hist:
            continue

        if hist["vola_7d"] < 22.0 and hist["position_7d"] < 0.48:
            item_with_hist = {
                **item,
                "vola_7d": hist["vola_7d"],
                "position_7d": round(hist["position_7d"] * 100, 1)
            }
            sideways.append(item_with_hist)
            print(f"  命中: {symbol}  7d波动={hist['vola_7d']}%  7d位置={hist['position_7d']*100:.1f}%")

    volatile.sort(key=lambda x: abs(x["change"]), reverse=True)
    sideways.sort(key=lambda x: x.get("vola_7d", 999))
    top_volume.sort(key=lambda x: x["volume"], reverse=True)

    print(f"最终横盘蓄势品种数量: {len(sideways)}")
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
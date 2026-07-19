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

def render_html(market_data):
    def fmt_price(p):
        if p >= 1000:
            return f"{p:,.2f}"
        elif p >= 1:
            return f"{p:,.4f}"
        elif p >= 0.001:
            return f"{p:,.6f}"
        else:
            return f"{p:.8f}"

    def fmt_volume(v):
        if v >= 1e9:
            return f"{v/1e9:.2f}B"
        elif v >= 1e6:
            return f"{v/1e6:.2f}M"
        elif v >= 1e3:
            return f"{v/1e3:.2f}K"
        return str(int(v))

    def get_change_class(c):
        return "color:#ff4d4f" if c >= 0 else "color:#52c41a"

    top_coins_html = ""
    if market_data.get("btc"):
        b = market_data["btc"]
        c = b["change24h"]
        top_coins_html += f"""
<div class="coin-card">
  <div class="coin-name">₿ BTC</div>
  <div class="coin-price">${fmt_price(b["price"])}</div>
  <div class="coin-change" style="{get_change_class(c)}">{'+' if c >= 0 else ''}{c:.2f}%</div>
  <a class="trade-btn" href="https://www.kxmqpwrlvjt.com/join/72697785" target="_blank" rel="nofollow noopener">去OKX交易 →</a>
</div>
"""
    if market_data.get("eth"):
        e = market_data["eth"]
        c = e["change24h"]
        top_coins_html += f"""
<div class="coin-card">
  <div class="coin-name">⟠ ETH</div>
  <div class="coin-price">${fmt_price(e["price"])}</div>
  <div class="coin-change" style="{get_change_class(c)}">{'+' if c >= 0 else ''}{c:.2f}%</div>
  <a class="trade-btn" href="https://www.kxmqpwrlvjt.com/join/72697785" target="_blank" rel="nofollow noopener">去OKX交易 →</a>
</div>
"""

    overview_html = f"""
<div class="ov-item"><div class="ov-label">总交易对</div><div class="ov-value">{market_data["totalPairs"]}</div></div>
<div class="ov-item"><div class="ov-label">上涨数量</div><div class="ov-value" style="color:#ff4d4f">{market_data["upCount"]}</div></div>
<div class="ov-item"><div class="ov-label">下跌数量</div><div class="ov-value" style="color:#52c41a">{market_data["downCount"]}</div></div>
<div class="ov-item"><div class="ov-label">24h成交额</div><div class="ov-value">${fmt_volume(market_data["totalVolume"])}</div></div>
<div class="ov-item"><div class="ov-label">市场情绪</div><div class="ov-value" style="color:{'#ff4d4f' if market_data['sentiment']=='bullish' else '#52c41a' if market_data['sentiment']=='bearish' else '#888'}">{'看涨' if market_data['sentiment']=='bullish' else '看跌' if market_data['sentiment']=='bearish' else '中性'}</div></div>
"""

    volatile_rows = ""
    for i, item in enumerate(market_data["volatile"][:20], 1):
        c = item["change"]
        volatile_rows += f"""
<tr>
  <td>{i}</td>
  <td>{item["symbol"]}</td>
  <td>${fmt_price(item["price"])}</td>
  <td style="{get_change_class(c)}">{'+' if c >= 0 else ''}{c:.2f}%</td>
  <td>${fmt_volume(item["volume"])}</td>
</tr>
"""

    sideways_rows = ""
    for i, item in enumerate(market_data["sideways"][:15], 1):
        c = item["change"]
        sideways_rows += f"""
<tr>
  <td>{i}</td>
  <td>{item["symbol"]}</td>
  <td>${fmt_price(item["price"])}</td>
  <td>{item.get("vola_7d", "N/A")}%</td>
  <td>{item.get("position_7d", "N/A")}%</td>
  <td style="{get_change_class(c)}">{'+' if c >= 0 else ''}{c:.2f}%</td>
</tr>
"""

    volume_rows = ""
    for i, item in enumerate(market_data["topVolume"][:10], 1):
        c = item["change"]
        volume_rows += f"""
<tr>
  <td>{i}</td>
  <td>{item["symbol"]}</td>
  <td>${fmt_price(item["price"])}</td>
  <td style="{get_change_class(c)}">{'+' if c >= 0 else ''}{c:.2f}%</td>
  <td>${fmt_volume(item["volume"])}</td>
</tr>
"""

    try:
        ts = datetime.fromisoformat(market_data["timestamp"])
        time_str = ts.strftime("%m-%d %H:%M")
    except:
        time_str = "刚刚"

    return {
        "top_coins": top_coins_html,
        "overview": overview_html,
        "volatile": volatile_rows,
        "sideways": sideways_rows,
        "volume": volume_rows,
        "update_time": f"⏰ {time_str}",
    }


def inject_data_into_html(market_data):
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            html = f.read()

        rendered = render_html(market_data)

        html = html.replace('<!-- SSR_DATA_TOP_COINS --><div class="loading">加载中...</div><!-- /SSR_DATA_TOP_COINS -->', rendered["top_coins"])
        html = html.replace('<!-- SSR_DATA_OVERVIEW --><div class="loading">加载中...</div><!-- /SSR_DATA_OVERVIEW -->', rendered["overview"])
        html = html.replace('<!-- SSR_DATA_VOLATILE --><tr><td colspan="5" class="loading">加载中...</td></tr><!-- /SSR_DATA_VOLATILE -->', rendered["volatile"])
        html = html.replace('<!-- SSR_DATA_SIDEWAYS --><tr><td colspan="6" class="loading">加载中...</td></tr><!-- /SSR_DATA_SIDEWAYS -->', rendered["sideways"])
        html = html.replace('<!-- SSR_DATA_VOLUME --><tr><td colspan="5" class="loading">加载中...</td></tr><!-- /SSR_DATA_VOLUME -->', rendered["volume"])
        html = html.replace('<div class="update-time" id="updateTime">⏰ 加载中...</div>', f'<div class="update-time" id="updateTime">{rendered["update_time"]}</div>')

        with open("index.html", "w", encoding="utf-8") as f:
            f.write(html)

        print("index.html 数据注入成功")
    except Exception as e:
        print(f"注入HTML失败: {e}")


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

    inject_data_into_html(market_data)

if __name__ == "__main__":
    main()
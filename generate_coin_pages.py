#!/usr/bin/env python3
"""
币种独立页面自动生成器
每小时数据更新时自动为异动品种生成/更新独立SEO页面
URL: signal.link.cn/coin/{SYMBOL}
"""
import json
import os
import re
import time
import urllib.request
import urllib.parse
from datetime import datetime, timedelta

# ── 配置 ──
SITE_URL = "https://signal.link.cn"
GA4_ID = "G-C0PKBWYHSD"
OKX_REF = "https://www.kxmqpwrlvjt.com/join/72697785"
BITGET_REF = "https://partner.hdmune.cn/bg/GD38XZ"
BINANCE_REF = "https://www.bsmkweb.cc/referral/earn-together/refer2earn-usdc/claim?hl=zh-CN&ref=GRO_28502_DUO1O&utm_source=referral_entrance"
INDEXNOW_KEY = "signalcrypto2026indexnow"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COIN_DIR = os.path.join(BASE_DIR, "coin")
HISTORY_FILE = os.path.join(BASE_DIR, "coin_history.json")

# ── 工具函数 ──
def fmt_price(p):
    if p >= 1000: return f"{p:,.2f}"
    elif p >= 1: return f"{p:,.4f}"
    elif p >= 0.001: return f"{p:,.6f}"
    else: return f"{p:.8f}"

def fmt_volume(v):
    if v >= 1e9: return f"{v/1e9:.2f}B"
    elif v >= 1e6: return f"{v/1e6:.2f}M"
    elif v >= 1e3: return f"{v/1e3:.2f}K"
    return str(int(v))

def get_symbol_name(inst_id):
    """BTC-USDT -> BTC"""
    return inst_id.split("-")[0] if "-" in inst_id else inst_id

def get_change_class(c):
    return "#ff4d4f" if c >= 0 else "#52c41a"

def get_change_text(c):
    return f"{'+' if c >= 0 else ''}{c:.2f}%"

# ── 历史异动记录管理 ──
def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {}

def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def update_history(market_data):
    """将当前异动记录追加到历史，保留30天"""
    history = load_history()
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    hour = now.strftime("%H:%M")

    all_coins = {}
    # 合并所有出现在列表中的币种
    for item in market_data.get("volatile", []):
        sym = get_symbol_name(item["symbol"])
        if sym not in all_coins:
            all_coins[sym] = item

    for item in market_data.get("sideways", []):
        sym = get_symbol_name(item["symbol"])
        if sym not in all_coins:
            all_coins[sym] = item

    for item in market_data.get("topVolume", []):
        sym = get_symbol_name(item["symbol"])
        if sym not in all_coins:
            all_coins[sym] = item

    for sym, item in all_coins.items():
        if sym not in history:
            history[sym] = {
                "symbol": sym,
                "first_seen": today,
                "records": []
            }

        # 避免同一天同一小时重复记录
        existing = [r for r in history[sym]["records"] if r.get("date") == today and r.get("time", "").startswith(hour[:2])]
        if not existing:
            record = {
                "date": today,
                "time": hour,
                "price": item["price"],
                "change": item["change"],
                "volume": item.get("volume", 0),
                "type": "volatile" if abs(item["change"]) >= 5 else "sideways" if "vola_7d" in item else "topVolume",
            }
            if "vola_7d" in item:
                record["vola_7d"] = item["vola_7d"]
                record["position_7d"] = item.get("position_7d", 0)
            history[sym]["records"].append(record)

    # 清理30天前的记录
    cutoff = (now - timedelta(days=30)).strftime("%Y-%m-%d")
    for sym in history:
        history[sym]["records"] = [r for r in history[sym]["records"] if r["date"] >= cutoff]
        history[sym]["last_updated"] = today

    # 清理没有记录的币种
    history = {k: v for k, v in history.items() if v["records"]}

    save_history(history)
    print(f"历史异动记录已更新: {len(history)} 个币种")
    return history

# ── 页面模板 ──
def generate_coin_page(symbol, coin_data, market_data, history):
    """生成单个币种的HTML页面"""
    sym = symbol
    inst_id = coin_data.get("symbol", f"{sym}-USDT")
    price = coin_data.get("price", 0)
    change = coin_data.get("change", 0)
    volume = coin_data.get("volume", 0)
    vola_7d = coin_data.get("vola_7d")
    position_7d = coin_data.get("position_7d")

    change_color = get_change_class(change)
    change_text = get_change_text(change)
    is_volatile = abs(change) >= 5
    is_sideways = vola_7d is not None and vola_7d < 22.0

    # 异动类型标签
    tags = []
    if is_volatile:
        tags.append(f'<span class="tag tag-volatile">⚡ 异动 {change_text}</span>')
    if is_sideways:
        tags.append('<span class="tag tag-sideways">📊 横盘蓄势</span>')
    if not tags:
        tags.append('<span class="tag tag-normal">📈 热门品种</span>')

    # 标题
    title_direction = "大涨" if change >= 5 else "大跌" if change <= -5 else "行情"
    page_title = f"{sym} {title_direction} {change_text} | {sym}币实时行情与异动分析 - Signal"
    meta_desc = f"{sym}币今日价格 ${fmt_price(price)}，24h涨跌 {change_text}，成交量 ${fmt_volume(volume)}。{sym}实时行情、历史异动记录、交易所注册链接，加密货币异动监控。"

    # 历史记录
    coin_history = history.get(sym, {})
    records = coin_history.get("records", [])
    history_html = ""
    if records:
        recent_records = sorted(records, key=lambda x: f"{x['date']} {x['time']}", reverse=True)[:20]
        for r in recent_records:
            r_color = get_change_class(r["change"])
            r_text = get_change_text(r["change"])
            r_type = r.get("type", "")
            type_label = {"volatile": "⚡异动", "sideways": "📊横盘", "topVolume": "📈热门"}.get(r_type, r_type)
            history_html += f"""
        <tr>
          <td>{r['date']}</td>
          <td>{r['time']}</td>
          <td>${fmt_price(r['price'])}</td>
          <td style="color:{r_color}">{r_text}</td>
          <td>${fmt_volume(r['volume'])}</td>
          <td><span class="tag-mini">{type_label}</span></td>
        </tr>"""
    else:
        history_html = '<tr><td colspan="6" class="empty">暂无历史异动记录，首次监控中</td></tr>'

    # 相关币种（同列表中的其他币种）
    related = []
    source_list = market_data.get("volatile", []) if is_volatile else market_data.get("sideways", []) if is_sideways else market_data.get("topVolume", [])
    for item in source_list:
        rel_sym = get_symbol_name(item["symbol"])
        if rel_sym != sym and len(related) < 6:
            related.append(item)
    related_html = ""
    if related:
        for item in related:
            rel_sym = get_symbol_name(item["symbol"])
            rel_c = item["change"]
            related_html += f"""
        <a href="/coin/{rel_sym}" class="related-coin">
          <div class="rc-symbol">{rel_sym}</div>
          <div class="rc-price">${fmt_price(item['price'])}</div>
          <div class="rc-change" style="color:{get_change_class(rel_c)}">{get_change_text(rel_c)}</div>
        </a>"""

    # Schema.org JSON-LD
    schema_crypto = {
        "@context": "https://schema.org",
        "@type": "CryptoCurrency",
        "name": sym,
        "symbol": sym,
        "url": f"{SITE_URL}/coin/{sym}",
        "description": f"{sym}币实时价格、异动监控与历史行情分析",
        "identifier": inst_id,
    }
    schema_breadcrumb = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "首页", "item": SITE_URL},
            {"@type": "ListItem", "position": 2, "name": "币种行情", "item": f"{SITE_URL}/#volatile"},
            {"@type": "ListItem", "position": 3, "name": sym, "item": f"{SITE_URL}/coin/{sym}"},
        ]
    }
    schema_faq = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": f"{sym}币今天价格是多少？",
                "acceptedAnswer": {"@type": "Answer", "text": f"{sym}币当前价格为 ${fmt_price(price)}，24小时涨跌 {change_text}，24小时成交额 ${fmt_volume(volume)}。数据来自OKX交易所实时行情。"}
            },
            {
                "@type": "Question",
                "name": f"{sym}今天为什么{'涨' if change > 0 else '跌'}？",
                "acceptedAnswer": {"@type": "Answer", "text": f"{sym}币24小时{'上涨' if change > 0 else '下跌'} {change_text}，{'属于异动品种（涨跌幅超过5%），' if is_volatile else ''}可能与市场情绪、资金流向、行业新闻等因素有关。建议关注成交量和7日波动率综合判断。"}
            },
            {
                "@type": "Question",
                "name": f"在哪里可以交易{sym}币？",
                "acceptedAnswer": {"@type": "Answer", "text": f"可以通过OKX、Bitget、Binance等主流交易所交易{sym}币。本页面提供注册链接，享受返佣优惠。"}
            }
        ]
    }

    # 7d数据展示
    vola_7d_html = f'<div class="stat-item"><div class="stat-label">7d波动率</div><div class="stat-value">{vola_7d}%</div></div>' if vola_7d is not None else ""
    pos_7d_html = f'<div class="stat-item"><div class="stat-label">7d价格位置</div><div class="stat-value">{position_7d}%</div></div>' if position_7d is not None else ""

    # 市场情绪
    sentiment = market_data.get("sentiment", "neutral")
    sentiment_text = {"bullish": "看涨", "bearish": "看跌", "neutral": "中性"}.get(sentiment, "中性")
    sentiment_color = "#ff4d4f" if sentiment == "bullish" else "#52c41a" if sentiment == "bearish" else "#888"

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    total_pairs = market_data.get("totalPairs", 0)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{page_title}</title>
<meta name="description" content="{meta_desc}">
<meta name="keywords" content="{sym},{sym}币,{sym}价格,{sym}行情,{sym}异动,{sym}今天为什么涨,{sym}实时价格,加密货币异动">
<link rel="canonical" href="{SITE_URL}/coin/{sym}">
<meta property="og:type" content="article">
<meta property="og:title" content="{page_title}">
<meta property="og:description" content="{meta_desc}">
<meta property="og:url" content="{SITE_URL}/coin/{sym}">
<meta property="og:site_name" content="Signal 加密货币分析">
<meta property="og:locale" content="zh_CN">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{page_title}">
<meta name="twitter:description" content="{meta_desc}">
<script async src="https://www.googletagmanager.com/gtag/js?id={GA4_ID}"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', '{GA4_ID}', {{'page_title': '{sym} 行情分析'}});
</script>
<script type="application/ld+json">{json.dumps(schema_crypto, ensure_ascii=False)}</script>
<script type="application/ld+json">{json.dumps(schema_breadcrumb, ensure_ascii=False)}</script>
<script type="application/ld+json">{json.dumps(schema_faq, ensure_ascii=False)}</script>
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0a0a0a;color:#e0e0e0;line-height:1.6;}}
.container{{max-width:900px;margin:0 auto;padding:0 16px;}}
nav{{background:#111;padding:12px 0;border-bottom:1px solid #222;position:sticky;top:0;z-index:100;}}
nav .container{{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;}}
nav .logo{{font-size:20px;font-weight:700;color:#f97316;text-decoration:none;}}
nav .links{{display:flex;gap:16px;flex-wrap:wrap;}}
nav .links a{{color:#888;text-decoration:none;font-size:14px;}}
nav .links a:hover{{color:#f97316;}}
.header{{padding:24px 0 16px;}}
.header h1{{font-size:28px;margin-bottom:8px;}}
.header h1 .sym{{color:#f97316;}}
.header .tags{{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px;}}
.tag{{display:inline-block;padding:4px 12px;border-radius:4px;font-size:13px;font-weight:600;}}
.tag-volatile{{background:rgba(255,77,79,0.15);color:#ff4d4f;}}
.tag-sideways{{background:rgba(82,196,26,0.15);color:#52c41a;}}
.tag-normal{{background:rgba(249,115,22,0.15);color:#f97316;}}
.tag-mini{{font-size:11px;padding:2px 6px;border-radius:3px;background:#333;color:#aaa;}}
.update-time{{font-size:12px;color:#666;margin-top:8px;}}
.section{{margin:28px 0;}}
.section h2{{font-size:18px;color:#f97316;margin-bottom:12px;border-left:3px solid #f97316;padding-left:10px;}}
.stats-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;}}
.stat-item{{background:#141414;border:1px solid #222;border-radius:8px;padding:16px;text-align:center;}}
.stat-label{{font-size:12px;color:#888;margin-bottom:6px;}}
.stat-value{{font-size:22px;font-weight:700;color:#e0e0e0;}}
.stat-value.change-up{{color:#ff4d4f;}}
.stat-value.change-down{{color:#52c41a;}}
.table-wrap{{overflow-x:auto;}}
table{{width:100%;border-collapse:collapse;font-size:14px;}}
th{{background:#1a1a1a;color:#888;padding:10px 8px;text-align:left;border-bottom:1px solid #222;font-weight:600;}}
td{{padding:10px 8px;border-bottom:1px solid #1a1a1a;}}
tr:hover{{background:#141414;}}
.empty{{text-align:center;color:#666;padding:20px;}}
.exchange-cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;}}
.exchange-card{{background:#141414;border:1px solid #222;border-radius:8px;padding:20px;text-align:center;}}
.exchange-card .ex-name{{font-size:18px;font-weight:700;margin-bottom:8px;}}
.exchange-card .ex-desc{{font-size:12px;color:#888;margin-bottom:12px;}}
.exchange-card .ex-btn{{display:inline-block;padding:10px 24px;border-radius:6px;text-decoration:none;font-size:14px;font-weight:600;}}
.ex-okx{{color:#fff;background:#f97316;}}
.ex-bitget{{color:#fff;background:#00c853;}}
.ex-binance{{color:#fff;background:#f0b90b;}}
.related-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px;}}
.related-coin{{display:block;background:#141414;border:1px solid #222;border-radius:8px;padding:14px;text-align:center;text-decoration:none;color:#e0e0e0;transition:border-color .2s;}}
.related-coin:hover{{border-color:#f97316;}}
.rc-symbol{{font-size:16px;font-weight:700;margin-bottom:4px;}}
.rc-price{{font-size:13px;color:#888;}}
.rc-change{{font-size:13px;margin-top:2px;}}
.disclaimer{{font-size:12px;color:#666;margin:28px 0;padding:16px;background:#0f0f0f;border-radius:8px;border:1px solid #1a1a1a;}}
footer{{background:#111;padding:24px 0;border-top:1px solid #222;}}
footer .links{{display:flex;gap:16px;flex-wrap:wrap;justify-content:center;margin-bottom:12px;}}
footer .links a{{color:#888;text-decoration:none;font-size:13px;}}
footer .copyright{{text-align:center;color:#555;font-size:12px;}}
@media(max-width:600px){{.header h1{{font-size:22px;}}.stat-value{{font-size:18px;}}}}
</style>
</head>
<body>
<nav>
  <div class="container">
    <a class="logo" href="/">₿ Signal</a>
    <div class="links">
      <a href="/">行情</a>
      <a href="/funding.html">资金费率</a>
      <a href="/tools.html">工具</a>
      <a href="/compare.html">交易所对比</a>
      <a href="https://prompts.link.cn" target="_blank" rel="nofollow">提示词</a>
    </div>
  </div>
</nav>

<div class="container">
  <div class="header">
    <h1><span class="sym">{sym}</span> 实时行情与异动分析</h1>
    <div class="tags">{''.join(tags)}</div>
    <div class="update-time">⏰ 数据更新于 {now_str} | 监控 {total_pairs} 个交易对 | 市场情绪: <span style="color:{sentiment_color}">{sentiment_text}</span></div>
  </div>

  <!-- 模块1: 实时数据 -->
  <div class="section">
    <h2>📊 {sym} 实时数据</h2>
    <div class="stats-grid">
      <div class="stat-item">
        <div class="stat-label">当前价格</div>
        <div class="stat-value">${fmt_price(price)}</div>
      </div>
      <div class="stat-item">
        <div class="stat-label">24h涨跌</div>
        <div class="stat-value {'change-up' if change >= 0 else 'change-down'}">{change_text}</div>
      </div>
      <div class="stat-item">
        <div class="stat-label">24h成交额</div>
        <div class="stat-value">${fmt_volume(volume)}</div>
      </div>
      {vola_7d_html}
      {pos_7d_html}
    </div>
  </div>

  <!-- 模块2: 历史异动记录 -->
  <div class="section">
    <h2>📜 {sym} 历史异动记录（近30天）</h2>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>日期</th>
            <th>时间</th>
            <th>价格</th>
            <th>涨跌幅</th>
            <th>成交额</th>
            <th>类型</th>
          </tr>
        </thead>
        <tbody>
          {history_html}
        </tbody>
      </table>
    </div>
  </div>

  <!-- 模块3: 异动归因 -->
  <div class="section">
    <h2>🔍 {sym} 异动分析</h2>
    <div style="background:#141414;border:1px solid #222;border-radius:8px;padding:20px;">
      <p style="margin-bottom:12px;">{sym}币24小时{'上涨' if change > 0 else '下跌'} <span style="color:{change_color};font-weight:700;">{change_text}</span>，{'触发异动警报（涨跌幅超过±5%），' if is_volatile else '处于正常波动区间，'}当前成交额 ${fmt_volume(volume)}。</p>
      <p style="margin-bottom:12px;">{'7日波动率 ' + str(vola_7d) + '%，价格处于7日区间 ' + str(position_7d) + '% 位置，' if vola_7d is not None else ''}{'属于横盘蓄势品种，可能即将突破。' if is_sideways else '波动较为活跃。'}</p>
      <p style="color:#888;font-size:13px;">💡 异动可能原因：市场资金流向变化、行业利好/利空消息、大盘联动效应、鲸鱼钱包异动等。建议结合成交量和市场情绪综合判断。</p>
    </div>
  </div>

  <!-- 模块4: 交易所注册链接 -->
  <div class="section">
    <h2>🏦 交易 {sym}</h2>
    <div class="exchange-cards">
      <div class="exchange-card">
        <div class="ex-name" style="color:#f97316;">OKX</div>
        <div class="ex-desc">全球领先交易所<br>注册享返佣</div>
        <a class="ex-btn ex-okx" href="{OKX_REF}" target="_blank" rel="nofollow noopener">注册交易 {sym} →</a>
      </div>
      <div class="exchange-card">
        <div class="ex-name" style="color:#00c853;">Bitget</div>
        <div class="ex-desc">跟单交易<br>合约杠杆</div>
        <a class="ex-btn ex-bitget" href="{BITGET_REF}" target="_blank" rel="nofollow noopener">注册交易 {sym} →</a>
      </div>
      <div class="exchange-card">
        <div class="ex-name" style="color:#f0b90b;">Binance</div>
        <div class="ex-desc">最大交易所<br>流动性最好</div>
        <a class="ex-btn ex-binance" href="{BINANCE_REF}" target="_blank" rel="nofollow noopener">注册交易 {sym} →</a>
      </div>
    </div>
  </div>

  <!-- 模块6: 相关币种推荐 -->
  {'<div class="section"><h2>📡 相关币种</h2><div class="related-grid">' + related_html + '</div></div>' if related_html else ''}

  <div class="disclaimer">
    ⚠️ 风险提示：以上数据来自OKX交易所公开API，仅供参考，不构成投资建议。加密货币投资有重大风险，请充分了解风险后谨慎决策。页面数据每小时自动更新。
  </div>
</div>

<footer>
  <div class="links">
    <a href="/">首页</a>
    <a href="/funding.html">资金费率</a>
    <a href="/tools.html">交易工具</a>
    <a href="/compare.html">交易所对比</a>
    <a href="/guide/btc-analysis.html">BTC分析</a>
    <a href="/guide/eth-analysis.html">ETH分析</a>
    <a href="https://ai.link.cn" target="_blank" rel="nofollow">AI资讯</a>
    <a href="https://tool.link.cn" target="_blank" rel="nofollow">AI工具</a>
    <a href="https://prompts.link.cn" target="_blank" rel="nofollow">提示词</a>
  </div>
  <div class="copyright">© 2026 Signal.link.cn · 加密货币异动监控 · 数据来自OKX</div>
</footer>

</body>
</html>"""

    return html

# ── sitemap 生成 ──
def update_sitemap(coin_symbols):
    """更新sitemap.xml，包含所有币种页面"""
    now = datetime.now().strftime("%Y-%m-%d")

    # 固定页面
    static_urls = [
        (f"{SITE_URL}/", "1.0", "daily"),
        (f"{SITE_URL}/funding.html", "0.9", "daily"),
        (f"{SITE_URL}/guide/btc-analysis.html", "0.9", "daily"),
        (f"{SITE_URL}/guide/eth-analysis.html", "0.9", "daily"),
        (f"{SITE_URL}/sitemap.html", "0.8", "weekly"),
        (f"{SITE_URL}/tools.html", "0.8", "weekly"),
        (f"{SITE_URL}/compare.html", "0.8", "weekly"),
        (f"{SITE_URL}/guide/spot-strategy.html", "0.8", "weekly"),
        (f"{SITE_URL}/guide/contract-trading.html", "0.8", "weekly"),
        (f"{SITE_URL}/guide/market-indicators.html", "0.8", "weekly"),
    ]

    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'

    for url, priority, changefreq in static_urls:
        xml += f"  <url>\n    <loc>{url}</loc>\n    <lastmod>{now}</lastmod>\n    <changefreq>{changefreq}</changefreq>\n    <priority>{priority}</priority>\n  </url>\n"

    # 币种页面
    for sym in sorted(coin_symbols):
        xml += f"  <url>\n    <loc>{SITE_URL}/coin/{sym}</loc>\n    <lastmod>{now}</lastmod>\n    <changefreq>hourly</changefreq>\n    <priority>0.7</priority>\n  </url>\n"

    xml += '</urlset>\n'

    sitemap_path = os.path.join(BASE_DIR, "sitemap.xml")
    with open(sitemap_path, "w", encoding="utf-8") as f:
        f.write(xml)
    print(f"sitemap.xml 已更新: {len(static_urls)} 固定 + {len(coin_symbols)} 币种 = {len(static_urls) + len(coin_symbols)} URL")

# ── IndexNow 提交 ──
def submit_indexnow(urls):
    """通过IndexNow协议提交URL到Bing/Yandex"""
    if not urls:
        return

    payload = {
        "host": "signal.link.cn",
        "key": INDEXNOW_KEY,
        "keyLocation": f"{SITE_URL}/{INDEXNOW_KEY}.txt",
        "urlList": urls[:200]  # IndexNow限制每次200个URL
    }

    # 写入key验证文件
    key_file = os.path.join(BASE_DIR, f"{INDEXNOW_KEY}.txt")
    with open(key_file, "w") as f:
        f.write(INDEXNOW_KEY)

    try:
        req = urllib.request.Request(
            "https://api.indexnow.org/IndexNow",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            print(f"IndexNow 提交: {resp.status} ({len(urls[:200])} URLs)")
    except Exception as e:
        print(f"IndexNow 提交失败: {e}")

# ── 主流程 ──
def main():
    # 读取data.json
    data_path = os.path.join(BASE_DIR, "data.json")
    if not os.path.exists(data_path):
        print("data.json 不存在，请先运行 generate_data.py")
        return

    with open(data_path, "r", encoding="utf-8") as f:
        market_data = json.load(f)

    print(f"加载市场数据: {market_data.get('totalPairs', 0)} 交易对, 时间: {market_data.get('timestamp', 'unknown')}")

    # 更新历史记录
    history = update_history(market_data)

    # 收集需要生成页面的币种
    coins_to_generate = {}

    for item in market_data.get("volatile", []):
        sym = get_symbol_name(item["symbol"])
        coins_to_generate[sym] = item

    for item in market_data.get("sideways", []):
        sym = get_symbol_name(item["symbol"])
        if sym not in coins_to_generate:
            coins_to_generate[sym] = item

    for item in market_data.get("topVolume", []):
        sym = get_symbol_name(item["symbol"])
        if sym not in coins_to_generate:
            coins_to_generate[sym] = item

    # 加入历史记录中有但当前不在列表的币种（保留页面，但更新数据）
    for sym, hist in history.items():
        if sym not in coins_to_generate and hist.get("records"):
            latest = hist["records"][-1]
            coins_to_generate[sym] = {
                "symbol": f"{sym}-USDT",
                "price": latest.get("price", 0),
                "change": latest.get("change", 0),
                "volume": latest.get("volume", 0),
            }

    print(f"待生成币种页面: {len(coins_to_generate)} 个")

    # 创建coin目录
    os.makedirs(COIN_DIR, exist_ok=True)

    # 生成页面
    generated_symbols = []
    new_urls = []

    for sym, coin_data in coins_to_generate.items():
        html = generate_coin_page(sym, coin_data, market_data, history)
        page_path = os.path.join(COIN_DIR, f"{sym}.html")
        with open(page_path, "w", encoding="utf-8") as f:
            f.write(html)
        generated_symbols.append(sym)
        new_urls.append(f"{SITE_URL}/coin/{sym}")

    print(f"已生成 {len(generated_symbols)} 个币种页面")

    # 更新sitemap
    update_sitemap(generated_symbols)

    # IndexNow 提交（只提交新的或更新的URL）
    submit_indexnow(new_urls)

    print("币种页面生成完成！")

if __name__ == "__main__":
    main()

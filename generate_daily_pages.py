#!/usr/bin/env python3
"""
每日异动汇总页面生成器
每日 0:00 CST 自动生成前一日快照页
URL: signal.link.cn/daily/{YYYY-MM-DD}

页面内容：
1. 当日异动 Top 10 排行榜
2. 横盘启动关注列表
3. 成交量 Top 10 变化
4. 交易所返佣链接
5. 上一日/下一日导航
6. Schema.org Article 结构化数据
"""
import json
import os
import re
import sys
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone

# ── 配置 ──
SITE_URL = "https://signal.link.cn"
GA4_ID = "G-C0PKBWYHSD"
OKX_REF = "https://www.kxmqpwrlvjt.com/join/72697785"
BITGET_REF = "https://partner.hdmune.cn/bg/GD38XZ"
BINANCE_REF = "https://www.bsmkweb.cc/referral/earn-together/refer2earn-usdc/claim?hl=zh-CN&ref=GRO_28502_DUO1O&utm_source=referral_entrance"
INDEXNOW_KEY = "signalcrypto2026indexnow"
DAILY_DIR_NAME = "daily"
RETENTION_DAYS = 90  # 保留最近90天的日报页面

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DAILY_DIR = os.path.join(BASE_DIR, DAILY_DIR_NAME)
DAILY_INDEX_FILE = os.path.join(BASE_DIR, "daily_index.json")
DAILY_DATA_DIR = os.path.join(BASE_DIR, "daily_data")  # 每日数据快照目录


# ── 工具函数 ──
def fmt_price(p):
    if p is None:
        return "N/A"
    if p >= 1000:
        return f"{p:,.2f}"
    elif p >= 1:
        return f"{p:,.4f}"
    elif p >= 0.001:
        return f"{p:,.6f}"
    else:
        return f"{p:.8f}"


def fmt_volume(v):
    if v is None:
        return "N/A"
    if v >= 1e9:
        return f"${v/1e9:.2f}B"
    elif v >= 1e6:
        return f"${v/1e6:.2f}M"
    elif v >= 1e3:
        return f"${v/1e3:.2f}K"
    return f"${int(v)}"


def get_symbol_name(inst_id):
    return inst_id.split("-")[0] if "-" in inst_id else inst_id


def get_change_class(c):
    return "#ff4d4f" if c >= 0 else "#52c41a"


def get_change_text(c):
    return f"{'+' if c >= 0 else ''}{c:.2f}%"


# ── 日报索引管理 ──
def load_daily_index():
    if os.path.exists(DAILY_INDEX_FILE):
        try:
            with open(DAILY_INDEX_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"dates": []}


def save_daily_index(index):
    with open(DAILY_INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


def add_to_daily_index(date_str, summary):
    """添加日期到日报索引，保留最近 RETENTION_DAYS 天"""
    index = load_daily_index()
    index["dates"] = [d for d in index["dates"] if d.get("date") != date_str]
    index["dates"].append({
        "date": date_str,
        "url": f"{SITE_URL}/daily/{date_str}",
        "generated_at": datetime.now().isoformat(),
        "volatile_count": summary.get("volatile_count", 0),
        "sideways_count": summary.get("sideways_count", 0),
        "top_symbol": summary.get("top_symbol", ""),
        "top_change": summary.get("top_change", 0),
        "sentiment": summary.get("sentiment", "neutral"),
    })
    index["dates"].sort(key=lambda x: x["date"])
    if len(index["dates"]) > RETENTION_DAYS:
        index["dates"] = index["dates"][-RETENTION_DAYS:]
    save_daily_index(index)
    return index


# ── HTML 生成 ──
def generate_daily_html(date_str, market_data, prev_date, next_date):
    """生成每日异动汇总页面 HTML"""
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    date_display = date_obj.strftime("%Y年%m月%d日")
    weekday_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][date_obj.weekday()]

    volatile = market_data.get("volatile", [])[:10]
    sideways = market_data.get("sideways", [])[:10]
    top_volume = market_data.get("topVolume", [])[:10]
    btc = market_data.get("btc")
    eth = market_data.get("eth")
    sentiment = market_data.get("sentiment", "neutral")

    sentiment_text = {"bullish": "看涨", "bearish": "看跌", "neutral": "中性"}.get(sentiment, "中性")
    sentiment_emoji = {"bullish": "🟢", "bearish": "🔴", "neutral": "🟡"}.get(sentiment, "🟡")
    sentiment_color = "#ff4d4f" if sentiment == "bullish" else "#52c41a" if sentiment == "bearish" else "#888"

    total_pairs = market_data.get("totalPairs", 0)
    up_count = market_data.get("upCount", 0)
    down_count = market_data.get("downCount", 0)
    total_volume = market_data.get("totalVolume", 0)

    top_volatile = volatile[0] if volatile else None
    top_summary = ""
    if top_volatile:
        top_sym = get_symbol_name(top_volatile["symbol"])
        top_change = top_volatile["change"]
        direction = "上涨" if top_change >= 0 else "下跌"
        top_summary = f"当日最大异动：{top_sym} {direction} {abs(top_change):.2f}%。"

    page_title = f"{date_display} 加密货币异动日报 | Signal"
    meta_desc = f"{date_display}（{weekday_cn}）加密货币市场异动汇总：{len(volatile)}个异动品种、{len(sideways)}个横盘关注、成交额{fmt_volume(total_volume)}。{top_summary}Signal.link.cn 每日自动生成。"

    # 模块1: 异动 Top 10 表格
    volatile_rows = ""
    for i, item in enumerate(volatile, 1):
        sym = get_symbol_name(item["symbol"])
        c = item["change"]
        volatile_rows += f"""
<tr>
  <td>{i}</td>
  <td><a href="/coin/{sym}" class="sym-link">{sym}</a></td>
  <td>${fmt_price(item['price'])}</td>
  <td style="color:{get_change_class(c)};font-weight:600">{get_change_text(c)}</td>
  <td>{fmt_volume(item['volume'])}</td>
</tr>"""

    volatile_section = f"""
<div class="section">
  <h2>⚡ 当日异动 Top {len(volatile)} 排行榜</h2>
  <p class="section-desc">24小时涨跌幅超过 5% 的品种，按绝对涨跌幅排序</p>
  <div class="table-wrap">
    <table>
      <thead><tr><th>#</th><th>币种</th><th>价格</th><th>24h涨跌</th><th>24h成交</th></tr></thead>
      <tbody>{volatile_rows if volatile_rows else '<tr><td colspan="5" class="empty">当日无明显异动品种</td></tr>'}</tbody>
    </table>
  </div>
</div>""" if volatile else """
<div class="section">
  <h2>⚡ 当日异动 Top 10 排行榜</h2>
  <p class="empty">当日无明显异动品种（涨跌幅均未超过 5%）</p>
</div>"""

    # 模块2: 横盘启动关注
    sideways_rows = ""
    for i, item in enumerate(sideways, 1):
        sym = get_symbol_name(item["symbol"])
        c = item.get("change", 0)
        vola_7d = item.get("vola_7d", "N/A")
        pos_7d = item.get("position_7d", "N/A")
        sideways_rows += f"""
<tr>
  <td>{i}</td>
  <td><a href="/coin/{sym}" class="sym-link">{sym}</a></td>
  <td>${fmt_price(item['price'])}</td>
  <td>{vola_7d}%</td>
  <td>{pos_7d}%</td>
  <td style="color:{get_change_class(c)}">{get_change_text(c)}</td>
</tr>"""

    sideways_section = f"""
<div class="section">
  <h2>📊 横盘启动关注列表</h2>
  <p class="section-desc">7日波动率较低、价格接近区间底部的品种，可能处于蓄势启动阶段</p>
  <div class="table-wrap">
    <table>
      <thead><tr><th>#</th><th>币种</th><th>价格</th><th>7d波动率</th><th>7d位置</th><th>24h涨跌</th></tr></thead>
      <tbody>{sideways_rows if sideways_rows else '<tr><td colspan="6" class="empty">当日无横盘蓄势品种</td></tr>'}</tbody>
    </table>
  </div>
</div>"""

    # 模块3: 成交量 Top 10
    volume_rows = ""
    for i, item in enumerate(top_volume, 1):
        sym = get_symbol_name(item["symbol"])
        c = item.get("change", 0)
        volume_rows += f"""
<tr>
  <td>{i}</td>
  <td><a href="/coin/{sym}" class="sym-link">{sym}</a></td>
  <td>${fmt_price(item['price'])}</td>
  <td style="color:{get_change_class(c)}">{get_change_text(c)}</td>
  <td>{fmt_volume(item['volume'])}</td>
</tr>"""

    volume_section = f"""
<div class="section">
  <h2>💰 成交量 Top {len(top_volume)} 变化</h2>
  <p class="section-desc">24h成交额最大的品种，反映市场资金主要流向</p>
  <div class="table-wrap">
    <table>
      <thead><tr><th>#</th><th>币种</th><th>价格</th><th>24h涨跌</th><th>24h成交</th></tr></thead>
      <tbody>{volume_rows if volume_rows else '<tr><td colspan="5" class="empty">无数据</td></tr>'}</tbody>
    </table>
  </div>
</div>"""

    # 模块4: 交易所返佣链接
    promo_section = f"""
<div class="section promo-section">
  <h2>🏦 交易所注册（返佣支持本站运营）</h2>
  <p class="section-desc">通过以下链接注册交易，你将获得手续费折扣，本站也能获得返佣支持</p>
  <div class="promo-grid">
    <a class="trade-btn okx" href="{OKX_REF}" target="_blank" rel="nofollow noopener">OKX 注册 → 享返佣</a>
    <a class="trade-btn bitget" href="{BITGET_REF}" target="_blank" rel="nofollow noopener">Bitget 注册 → 享返佣</a>
    <a class="trade-btn binance" href="{BINANCE_REF}" target="_blank" rel="nofollow noopener">Binance 注册</a>
  </div>
</div>"""

    # 模块5: 上一日/下一日导航
    nav_prev = f'<a href="/daily/{prev_date}" class="nav-btn nav-prev">← {prev_date}</a>' if prev_date else '<span class="nav-btn nav-disabled">← 无更早日报</span>'
    nav_next = f'<a href="/daily/{next_date}" class="nav-btn nav-next">{next_date} →</a>' if next_date else '<span class="nav-btn nav-disabled nav-next">暂无下一日日报 →</span>'

    nav_section = f"""
<div class="daily-nav">
  {nav_prev}
  <a href="/" class="nav-btn nav-home">🏠 返回首页</a>
  {nav_next}
</div>"""

    # 模块6: Schema.org Article 结构化数据
    schema_article = {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": f"{date_display} 加密货币异动日报",
        "description": meta_desc,
        "datePublished": f"{date_str}T00:00:00+08:00",
        "dateModified": datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "author": {
            "@type": "Organization",
            "name": "Signal.link.cn",
            "url": SITE_URL
        },
        "publisher": {
            "@type": "Organization",
            "name": "Signal 加密货币分析",
            "logo": {
                "@type": "ImageObject",
                "url": f"{SITE_URL}/og-image.jpg"
            }
        },
        "mainEntityOfPage": {
            "@type": "WebPage",
            "@id": f"{SITE_URL}/daily/{date_str}"
        },
        "image": f"{SITE_URL}/og-image.jpg",
        "articleSection": "加密货币市场分析",
        "keywords": f"{date_display},加密货币日报,异动汇总,比特币,以太坊,行情分析,{date_str}",
    }

    schema_breadcrumb = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "首页", "item": SITE_URL},
            {"@type": "ListItem", "position": 2, "name": "每日异动日报", "item": f"{SITE_URL}/#daily-reports"},
            {"@type": "ListItem", "position": 3, "name": date_str, "item": f"{SITE_URL}/daily/{date_str}"},
        ]
    }

    # BTC/ETH 卡片
    btc_card = ""
    if btc:
        c = btc.get("change24h", 0)
        btc_card = f"""
<div class="hero-card">
  <div class="hero-name">₿ BTC</div>
  <div class="hero-price">${fmt_price(btc['price'])}</div>
  <div class="hero-change" style="color:{get_change_class(c)}">{get_change_text(c)}</div>
</div>"""
    eth_card = ""
    if eth:
        c = eth.get("change24h", 0)
        eth_card = f"""
<div class="hero-card">
  <div class="hero-name">⟠ ETH</div>
  <div class="hero-price">${fmt_price(eth['price'])}</div>
  <div class="hero-change" style="color:{get_change_class(c)}">{get_change_text(c)}</div>
</div>"""

    # 概览数据
    overview_html = f"""
<div class="ov-item"><div class="ov-label">监控品种</div><div class="ov-value">{total_pairs}</div></div>
<div class="ov-item"><div class="ov-label">上涨/下跌</div><div class="ov-value"><span style="color:#ff4d4f">↑{up_count}</span> / <span style="color:#52c41a">↓{down_count}</span></div></div>
<div class="ov-item"><div class="ov-label">24h成交额</div><div class="ov-value">{fmt_volume(total_volume)}</div></div>
<div class="ov-item"><div class="ov-label">市场情绪</div><div class="ov-value" style="color:{sentiment_color}">{sentiment_emoji} {sentiment_text}</div></div>
<div class="ov-item"><div class="ov-label">异动品种</div><div class="ov-value">{len(volatile)}</div></div>
<div class="ov-item"><div class="ov-label">横盘关注</div><div class="ov-value">{len(sideways)}</div></div>
"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{page_title}</title>
<meta name="description" content="{meta_desc}">
<meta name="keywords" content="{date_str},{date_display},加密货币日报,异动汇总,比特币行情,以太坊行情,加密货币异动,Signal 日报">
<link rel="canonical" href="{SITE_URL}/daily/{date_str}">
<meta property="og:type" content="article">
<meta property="og:title" content="{page_title}">
<meta property="og:description" content="{meta_desc}">
<meta property="og:url" content="{SITE_URL}/daily/{date_str}">
<meta property="og:site_name" content="Signal 加密货币分析">
<meta property="og:locale" content="zh_CN">
<meta property="og:image" content="{SITE_URL}/og-image.jpg">
<meta property="article:published_time" content="{date_str}T00:00:00+08:00">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{page_title}">
<meta name="twitter:description" content="{meta_desc}">
<meta name="robots" content="index, follow, max-image-preview:large">
<script async src="https://www.googletagmanager.com/gtag/js?id={GA4_ID}"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', '{GA4_ID}', {{'page_title': '{page_title}'}});
</script>
<script type="application/ld+json">{json.dumps(schema_article, ensure_ascii=False)}</script>
<script type="application/ld+json">{json.dumps(schema_breadcrumb, ensure_ascii=False)}</script>
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,"Noto Sans SC",sans-serif;background:linear-gradient(135deg,#0f0c29,#1a1a3e 40%,#24243e);color:#e0e0e0;min-height:100vh;padding:20px;}}
.container{{max-width:1200px;margin:0 auto;}}
header{{text-align:center;padding:30px 20px 20px;}}
.daily-badge{{display:inline-block;background:linear-gradient(90deg,#667eea,#764ba2);padding:6px 18px;border-radius:20px;font-size:.85em;color:#fff;margin-bottom:12px;}}
h1{{font-size:2em;background:linear-gradient(90deg,#667eea,#764ba2);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:8px;}}
.daily-date{{color:#aaa;font-size:1em;margin-bottom:6px;}}
.daily-meta{{color:#888;font-size:.85em;}}
.hero-cards{{display:flex;gap:20px;justify-content:center;margin:20px 0;flex-wrap:wrap;}}
.hero-card{{background:rgba(255,255,255,.06);backdrop-filter:blur(8px);border:1px solid rgba(255,255,255,.08);border-radius:16px;padding:20px 30px;min-width:200px;text-align:center;}}
.hero-name{{font-size:.9em;color:#888;margin-bottom:6px;}}
.hero-price{{font-size:1.6em;font-weight:700;color:#fff;}}
.hero-change{{font-size:1.1em;font-weight:600;margin-top:4px;}}
.section{{background:rgba(255,255,255,.04);backdrop-filter:blur(10px);border:1px solid rgba(255,255,255,.06);border-radius:16px;padding:25px;margin-bottom:25px;}}
h2{{font-size:1.4em;margin-bottom:12px;padding-bottom:10px;border-bottom:1px solid rgba(255,255,255,.08);}}
.section-desc{{color:#888;font-size:.85em;margin-bottom:18px;}}
.ov-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:15px;}}
.ov-item{{background:rgba(255,255,255,.05);border-radius:12px;padding:16px;text-align:center;}}
.ov-label{{font-size:.78em;color:#888;margin-bottom:6px;}}
.ov-value{{font-size:1.3em;font-weight:700;}}
.table-wrap{{overflow-x:auto;}}
table{{width:100%;border-collapse:collapse;font-size:.92em;}}
th{{background:rgba(255,255,255,.06);padding:10px 12px;text-align:left;font-weight:600;color:#999;font-size:.85em;white-space:nowrap;}}
td{{padding:10px 12px;border-bottom:1px solid rgba(255,255,255,.04);white-space:nowrap;}}
tr:hover td{{background:rgba(255,255,255,.03);}}
.sym-link{{color:#a8b1ff;text-decoration:none;font-weight:500;}}
.sym-link:hover{{text-decoration:underline;}}
.empty{{text-align:center;color:#888;padding:30px 12px;font-style:italic;}}
.promo-section{{background:linear-gradient(135deg,rgba(102,126,234,.12),rgba(118,75,162,.12));border:1px solid rgba(102,126,234,.2);}}
.promo-grid{{display:flex;gap:12px;justify-content:center;flex-wrap:wrap;margin-top:15px;}}
.trade-btn{{display:inline-block;padding:12px 28px;border-radius:30px;text-decoration:none;font-weight:600;font-size:.95em;transition:transform .2s;}}
.trade-btn:hover{{transform:translateY(-2px);}}
.trade-btn.okx{{background:linear-gradient(135deg,#1a1a3e,#2d4a8a);color:#fff;}}
.trade-btn.bitget{{background:linear-gradient(135deg,#00f5a0,#00d9f5);color:#0a0a0a;}}
.trade-btn.binance{{background:linear-gradient(135deg,#f0b90b,#f8d33d);color:#0a0a0a;}}
.daily-nav{{display:flex;justify-content:space-between;align-items:center;margin:30px 0;gap:12px;flex-wrap:wrap;}}
.nav-btn{{display:inline-block;padding:10px 20px;border-radius:8px;text-decoration:none;font-size:.9em;background:rgba(255,255,255,.06);color:#a8b1ff;border:1px solid rgba(255,255,255,.08);transition:background .2s;}}
.nav-btn:hover{{background:rgba(255,255,255,.12);}}
.nav-disabled{{color:#555;background:rgba(255,255,255,.02);cursor:not-allowed;}}
.nav-home{{color:#fff;}}
.disclaimer{{background:rgba(255,193,7,.08);border-left:3px solid #ffc107;padding:14px 18px;border-radius:8px;font-size:.85em;color:#bbb;margin-bottom:25px;}}
footer{{text-align:center;padding:30px;color:#555;font-size:.8em;}}
footer a{{color:#667eea;text-decoration:none;}}
footer .links{{margin-bottom:20px;display:flex;flex-wrap:wrap;gap:10px;justify-content:center;}}
</style>
</head>
<body>
<div class="container">

<header>
  <div class="daily-badge">📡 每日异动日报 · Daily Signal Report</div>
  <h1>{date_display} 加密货币异动汇总</h1>
  <div class="daily-date">{weekday_cn} · 数据快照</div>
  <div class="daily-meta">由 Signal.link.cn 自动生成 · 数据来源 OKX</div>
</header>

<div class="hero-cards">
  {btc_card}
  {eth_card}
</div>

<div class="section">
  <h2>📋 市场概览</h2>
  <div class="ov-grid">{overview_html}</div>
</div>

{volatile_section}

{sideways_section}

{volume_section}

{promo_section}

{nav_section}

<div class="disclaimer">
  ⚠️ 风险提示：以上数据来自 OKX 交易所公开 API，仅供参考，不构成投资建议。加密货币投资有重大风险，请充分了解风险后谨慎决策。本页面为当日数据快照，实时数据请访问首页。
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
  <p>© 2026 Signal.link.cn · 加密货币异动日报 · 数据来自 OKX</p>
</footer>

</div>
</body>
</html>"""

    return html


# ── 主流程 ──
def generate_for_date(date_str, market_data=None, prev_date=None, next_date=None):
    """为指定日期生成日报页面"""
    if market_data is None:
        data_path = os.path.join(BASE_DIR, "data.json")
        if os.path.exists(data_path):
            with open(data_path, "r", encoding="utf-8") as f:
                market_data = json.load(f)
        else:
            print(f"data.json 不存在，无法生成 {date_str} 的日报")
            return False

    os.makedirs(DAILY_DIR, exist_ok=True)

    html = generate_daily_html(date_str, market_data, prev_date, next_date)
    page_path = os.path.join(DAILY_DIR, f"{date_str}.html")

    with open(page_path, "w", encoding="utf-8") as f:
        f.write(html)

    volatile = market_data.get("volatile", [])
    sideways = market_data.get("sideways", [])
    top_sym = get_symbol_name(volatile[0]["symbol"]) if volatile else ""
    top_change = volatile[0].get("change", 0) if volatile else 0

    summary = {
        "volatile_count": len(volatile),
        "sideways_count": len(sideways),
        "top_symbol": top_sym,
        "top_change": top_change,
        "sentiment": market_data.get("sentiment", "neutral"),
    }

    add_to_daily_index(date_str, summary)
    print(f"已生成日报页面: /daily/{date_str} (异动 {len(volatile)} | 横盘 {len(sideways)})")
    return True


def get_existing_dates():
    """获取已生成的日报日期列表"""
    index = load_daily_index()
    return [d["date"] for d in index.get("dates", [])]


def find_neighbors(target_date, existing_dates):
    """在已生成日期列表中找到目标日期的前一天和后一天"""
    if not existing_dates:
        return None, None
    sorted_dates = sorted(existing_dates)
    try:
        idx = sorted_dates.index(target_date)
    except ValueError:
        prev = None
        nxt = None
        for d in sorted_dates:
            if d < target_date:
                prev = d
            elif d > target_date and nxt is None:
                nxt = d
                break
        return prev, nxt
    prev = sorted_dates[idx - 1] if idx > 0 else None
    nxt = sorted_dates[idx + 1] if idx < len(sorted_dates) - 1 else None
    return prev, nxt


def update_sitemap_daily(dates):
    """将 daily 页面追加到 sitemap.xml"""
    sitemap_path = os.path.join(BASE_DIR, "sitemap.xml")
    if not os.path.exists(sitemap_path):
        return

    try:
        with open(sitemap_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 移除已有的 daily 段
        content = re.sub(r'\s*<!-- daily-pages-start -->.*?<!-- daily-pages-end -->',
                         '', content, flags=re.DOTALL)

        content = content.replace('</urlset>', '')

        now = datetime.now().strftime("%Y-%m-%d")
        daily_block = "\n  <!-- daily-pages-start -->\n"
        # 日报汇总页
        daily_block += f"  <url>\n    <loc>{SITE_URL}/daily/</loc>\n    <lastmod>{now}</lastmod>\n    <changefreq>daily</changefreq>\n    <priority>0.8</priority>\n  </url>\n"
        # RSS Feed
        daily_block += f"  <url>\n    <loc>{SITE_URL}/feed.xml</loc>\n    <lastmod>{now}</lastmod>\n    <changefreq>daily</changefreq>\n    <priority>0.7</priority>\n  </url>\n"
        for d in sorted(dates):
            daily_block += f"  <url>\n    <loc>{SITE_URL}/daily/{d}</loc>\n    <lastmod>{now}</lastmod>\n    <changefreq>monthly</changefreq>\n    <priority>0.6</priority>\n  </url>\n"
        daily_block += "  <!-- daily-pages-end -->\n"

        content = content.rstrip() + "\n" + daily_block + "</urlset>\n"

        with open(sitemap_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"sitemap.xml 已更新: 新增 {len(dates)} 个 daily 页面")
    except Exception as e:
        print(f"更新 sitemap 失败: {e}")


def submit_indexnow(urls):
    """通过 IndexNow 协议提交 URL"""
    if not urls:
        return

    payload = {
        "host": "signal.link.cn",
        "key": INDEXNOW_KEY,
        "keyLocation": f"{SITE_URL}/{INDEXNOW_KEY}.txt",
        "urlList": urls[:200]
    }

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
            print(f"IndexNow 提交: {resp.status} ({len(urls)} URLs)")
    except Exception as e:
        print(f"IndexNow 提交失败: {e}")


def ping_google_sitemap():
    """主动 ping Google Search Console 来抓取 sitemap"""
    sitemap_url = urllib.parse.quote(f"{SITE_URL}/sitemap.xml", safe="")
    ping_url = f"https://www.google.com/ping?sitemap={sitemap_url}"
    try:
        req = urllib.request.Request(ping_url, method="GET")
        with urllib.request.urlopen(req, timeout=15) as resp:
            print(f"Google sitemap ping: {resp.status}")
    except Exception as e:
        print(f"Google sitemap ping 失败: {e}")


def ping_baidu_sitemap():
    """主动 ping 百度站长来抓取 sitemap"""
    sitemap_url = urllib.parse.quote(f"{SITE_URL}/sitemap.xml", safe="")
    ping_url = f"http://ping.baidu.com/ping/RPC2"
    # 百度使用 XML-RPC，这里简化处理用 GET 通知
    try:
        req = urllib.request.Request(
            f"https://www.baidu.com/s?wd=site:signal.link.cn",
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"Baidu ping: {resp.status}")
    except Exception as e:
        print(f"Baidu ping 失败: {e}")


def save_daily_snapshot(date_str, market_data):
    """保存每日数据快照到 daily_data/{date}.json"""
    os.makedirs(DAILY_DATA_DIR, exist_ok=True)
    snapshot_path = os.path.join(DAILY_DATA_DIR, f"{date_str}.json")
    with open(snapshot_path, "w", encoding="utf-8") as f:
        json.dump(market_data, f, ensure_ascii=False, indent=2)
    print(f"数据快照已保存: daily_data/{date_str}.json")


def load_daily_snapshot(date_str):
    """加载某个日期的数据快照"""
    snapshot_path = os.path.join(DAILY_DATA_DIR, f"{date_str}.json")
    if os.path.exists(snapshot_path):
        try:
            with open(snapshot_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None


def generate_rss_feed():
    """生成 RSS feed.xml，包含最近的日报和热门币种页面"""
    index = load_daily_index()
    dates = index.get("dates", [])[-15:]  # 最近15天
    dates.reverse()  # 最新在前

    # 从 data.json 获取热门币种
    data_path = os.path.join(BASE_DIR, "data.json")
    coin_items = []
    if os.path.exists(data_path):
        with open(data_path, "r", encoding="utf-8") as f:
            market_data = json.load(f)
        for item in market_data.get("volatile", [])[:5]:
            sym = get_symbol_name(item["symbol"])
            c = item["change"]
            direction = "上涨" if c >= 0 else "下跌"
            coin_items.append({
                "title": f"{sym} 24h{direction}{abs(c):.2f}% - 实时行情分析",
                "url": f"{SITE_URL}/coin/{sym}",
                "desc": f"{sym}币当前价格 ${fmt_price(item['price'])}，24h涨跌 {get_change_text(c)}，成交额 {fmt_volume(item['volume'])}。查看{sym}实时行情、历史异动、交易返佣。",
                "date": market_data.get("timestamp", ""),
            })

    now_rfc = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0800")

    items_xml = ""
    # 日报条目
    for d in dates:
        date_obj = datetime.strptime(d["date"], "%Y-%m-%d")
        pub_date = date_obj.strftime("%a, %d %b %Y 08:00:00 +0800")
        top_sym = d.get("top_symbol", "")
        top_change = d.get("top_change", 0)
        direction = "上涨" if top_change >= 0 else "下跌"
        vol_count = d.get("volatile_count", 0)
        side_count = d.get("sideways_count", 0)
        title = f"{d['date']} 加密货币异动日报: {vol_count}个异动, {side_count}个横盘"
        if top_sym:
            title += f" | 最大异动 {top_sym} {direction}{abs(top_change):.2f}%"
        desc = f"{d['date']} 市场快照：{vol_count}个异动品种、{side_count}个横盘关注品种。最大异动 {top_sym} {direction} {abs(top_change):.2f}%。"
        items_xml += f"""
        <item>
            <title>{title}</title>
            <link>{d['url']}</link>
            <guid isPermaLink="true">{d['url']}</guid>
            <description>{desc}</description>
            <pubDate>{pub_date}</pubDate>
        </item>"""

    # 币种条目
    for item in coin_items:
        pub_date = now_rfc
        if item["date"]:
            try:
                dt = datetime.fromisoformat(item["date"])
                pub_date = dt.strftime("%a, %d %b %Y %H:%M:%S +0800")
            except Exception:
                pass
        items_xml += f"""
        <item>
            <title>{item['title']}</title>
            <link>{item['url']}</link>
            <guid isPermaLink="true">{item['url']}</guid>
            <description>{item['desc']}</description>
            <pubDate>{pub_date}</pubDate>
        </item>"""

    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
    <channel>
        <title>Signal 加密货币分析 - 异动日报</title>
        <link>{SITE_URL}/</link>
        <description>加密货币市场异动监控、每日行情日报、横盘启动关注、实时价格分析</description>
        <language>zh-CN</language>
        <lastBuildDate>{now_rfc}</lastBuildDate>
        <atom:link href="{SITE_URL}/feed.xml" rel="self" type="application/rss+xml" />
{items_xml}
    </channel>
</rss>"""

    feed_path = os.path.join(BASE_DIR, "feed.xml")
    with open(feed_path, "w", encoding="utf-8") as f:
        f.write(rss)
    print(f"feed.xml 已生成: {len(dates)} 日报 + {len(coin_items)} 币种 = {len(dates) + len(coin_items)} 条")


def generate_daily_index_page():
    """生成 /daily/index.html 日报汇总页（hub page）"""
    index = load_daily_index()
    dates = index.get("dates", [])
    if not dates:
        print("无日报数据，跳过汇总页生成")
        return

    # 按日期倒序（最新在前）
    dates_sorted = sorted(dates, key=lambda x: x["date"], reverse=True)

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 构建日报列表行
    rows_html = ""
    for d in dates_sorted:
        date_obj = datetime.strptime(d["date"], "%Y-%m-%d")
        weekday_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][date_obj.weekday()]
        vol = d.get("volatile_count", 0)
        side = d.get("sideways_count", 0)
        top_sym = d.get("top_symbol", "")
        top_chg = d.get("top_change", 0)
        direction = "上涨" if top_chg >= 0 else "下跌"
        chg_color = "#ff4d4f" if top_chg >= 0 else "#52c41a"

        top_cell = ""
        if top_sym:
            top_cell = f'<a href="/coin/{top_sym}" style="color:{chg_color};text-decoration:none">{top_sym} {direction}{abs(top_chg):.2f}%</a>'

        rows_html += f"""        <tr>
          <td><a href="/daily/{d['date']}" style="color:#a8b1ff;text-decoration:none;font-weight:600">{d['date']}</a> <span style="color:#666;font-size:.85em">{weekday_cn}</span></td>
          <td style="text-align:center">{vol}</td>
          <td style="text-align:center">{side}</td>
          <td>{top_cell}</td>
        </tr>
"""

    # BreadcrumbList 结构化数据
    breadcrumb_json = json.dumps({
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "首页", "item": f"{SITE_URL}/"},
            {"@type": "ListItem", "position": 2, "name": "每日异动日报", "item": f"{SITE_URL}/daily/"},
        ]
    }, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>每日异动日报汇总 | Signal 加密货币分析</title>
<meta name="description" content="Signal 加密货币每日异动日报汇总页，包含每日市场异动排行榜、横盘启动关注列表、成交量变化分析。每日 0:00 自动生成前一日的市场快照。">
<meta name="keywords" content="加密货币日报,每日异动汇总,币圈日报,crypto daily report,异动排行榜,横盘启动">
<link rel="canonical" href="{SITE_URL}/daily/">
<meta property="og:type" content="website">
<meta property="og:title" content="每日异动日报汇总 | Signal 加密货币分析">
<meta property="og:description" content="每日市场异动排行榜、横盘启动关注列表、成交量变化分析">
<meta property="og:url" content="{SITE_URL}/daily/">
<meta property="og:site_name" content="Signal">
<link rel="alternate" type="application/rss+xml" title="Signal 异动日报 RSS" href="{SITE_URL}/feed.xml" />
<script async src="https://www.googletagmanager.com/gtag/js?id={GA4_ID}"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', '{GA4_ID}');
</script>
<script type="application/ld+json">{breadcrumb_json}</script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,"Noto Sans SC",sans-serif;background:linear-gradient(135deg,#0f0c29,#1a1a3e 40%,#24243e);color:#e0e0e0;min-height:100vh;padding:20px}}
.container{{max-width:1000px;margin:0 auto}}
header{{text-align:center;padding:40px 20px 20px}}
h1{{font-size:1.8em;background:linear-gradient(90deg,#667eea,#764ba2);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:8px}}
.subtitle{{color:#aaa;font-size:.9em;margin-bottom:15px}}
.breadcrumb{{color:#666;font-size:.82em;margin-bottom:20px}}
.breadcrumb a{{color:#a8b1ff;text-decoration:none}}
.section{{background:rgba(255,255,255,.04);backdrop-filter:blur(10px);border:1px solid rgba(255,255,255,.06);border-radius:16px;padding:25px;margin-bottom:25px}}
h2{{font-size:1.3em;margin-bottom:18px;padding-bottom:10px;border-bottom:1px solid rgba(255,255,255,.08)}}
.table-wrap{{overflow-x:auto}}
table{{width:100%;border-collapse:collapse;font-size:.9em}}
th{{background:rgba(255,255,255,.06);padding:10px 12px;text-align:left;font-weight:600;color:#999;font-size:.85em;white-space:nowrap}}
td{{padding:10px 12px;border-bottom:1px solid rgba(255,255,255,.04)}}
tr:hover td{{background:rgba(102,126,234,.06)}}}
.ref-links{{display:flex;gap:12px;justify-content:center;flex-wrap:wrap;margin-top:20px}}
.ref-btn{{display:inline-block;padding:10px 24px;border-radius:10px;text-decoration:none;font-size:.88em;font-weight:600}}
.back-home{{display:inline-block;margin-top:20px;padding:10px 24px;background:rgba(102,126,234,.15);color:#a8b1ff;border-radius:10px;text-decoration:none;font-size:.88em}}
.disclaimer{{color:#666;font-size:.8em;text-align:center;margin:20px 0;padding:0 20px}}
.update-info{{color:#666;font-size:.8em;text-align:center;margin-bottom:15px}}
</style>
</head>
<body>
<div class="container">
<header>
<h1>📰 每日异动日报汇总</h1>
<p class="subtitle">每日 0:00 自动生成前一日加密货币市场异动快照 · 数据来源 OKX</p>
<div class="breadcrumb"><a href="/">首页</a> / 每日异动日报</div>
</header>

<div class="section">
<h2>📅 历史日报列表（共 {len(dates_sorted)} 篇）</h2>
<p class="update-info">最后更新: {now_str} (北京时间)</p>
<div class="table-wrap">
<table>
<thead>
<tr><th>日期</th><th style="text-align:center">异动数</th><th style="text-align:center">横盘数</th><th>最大异动</th></tr>
</thead>
<tbody>
{rows_html}</tbody>
</table>
</div>
</div>

<div class="section">
<h2>🏦 交易所注册（返佣支持本站运营）</h2>
<div class="ref-links">
<a href="{OKX_REF}" target="_blank" class="ref-btn" style="background:rgba(0,0,0,.3);color:#fff">OKX 注册</a>
<a href="{BITGET_REF}" target="_blank" class="ref-btn" style="background:rgba(0,195,255,.15);color:#00c3ff">Bitget 注册</a>
<a href="{BINANCE_REF}" target="_blank" class="ref-btn" style="background:rgba(243,186,26,.15);color:#f3ba1a">Binance 注册</a>
</div>
</div>

<div style="text-align:center">
<a href="/" class="back-home">← 返回首页</a>
<a href="/feed.xml" class="back-home" style="margin-left:10px">📡 RSS 订阅</a>
</div>

<div class="disclaimer"><strong>⚠️ 风险提示：</strong>本分析仅供参考，不构成投资建议。加密货币风险极高，仅用闲钱参与。</div>
</div>
</body>
</html>"""

    index_path = os.path.join(DAILY_DIR, "index.html")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"/daily/index.html 已生成: {len(dates_sorted)} 篇日报")


def update_homepage_recent_section(dates):
    """在 index.html 中注入「最近 7 天异动日报」链接区"""
    index_path = os.path.join(BASE_DIR, "index.html")
    if not os.path.exists(index_path):
        print("index.html 不存在，跳过首页更新")
        return

    try:
        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()

        recent = sorted(dates)[-7:][::-1]

        if not recent:
            return

        links_html = ""
        for d in recent:
            date_obj = datetime.strptime(d, "%Y-%m-%d")
            weekday_cn = ["一", "二", "三", "四", "五", "六", "日"][date_obj.weekday()]
            links_html += f'<a href="/daily/{d}" class="daily-link">📅 {d} (周{weekday_cn}) →</a>\n'

        section_block = f"""
<div class="section" id="daily-reports">
  <h2>📰 最近 7 天异动日报</h2>
  <p style="color:#888;font-size:.85em;margin-bottom:18px">每日 0:00 自动生成前一日的市场异动快照，可点击查看历史行情</p>
  <div class="daily-links">
{links_html}  </div>
</div>

"""

        # 用 SSR 标记替换（如果标记存在），否则插入到 disclaimer 前
        pattern = r'<!-- SSR_DAILY_REPORTS -->.*?<!-- /SSR_DAILY_REPORTS -->'
        if re.search(pattern, html, flags=re.DOTALL):
            html = re.sub(pattern,
                          f'<!-- SSR_DAILY_REPORTS -->{section_block}<!-- /SSR_DAILY_REPORTS -->',
                          html, flags=re.DOTALL)
        else:
            insert_pattern = r'<div class="disclaimer">'
            if re.search(insert_pattern, html):
                html = re.sub(insert_pattern,
                              f'{section_block}<div class="disclaimer">',
                              html, count=1)
            else:
                html = re.sub(r'<footer>',
                              f'{section_block}<footer>',
                              html, count=1)

        with open(index_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"index.html 已注入「最近 7 天异动日报」区: {len(recent)} 个链接")
    except Exception as e:
        print(f"更新 index.html 失败: {e}")


def cleanup_old_pages():
    """删除超过 RETENTION_DAYS 天的旧日报页面"""
    if not os.path.exists(DAILY_DIR):
        return []

    cutoff = datetime.now() - timedelta(days=RETENTION_DAYS)
    cutoff_str = cutoff.strftime("%Y-%m-%d")
    removed = []

    for fname in os.listdir(DAILY_DIR):
        if not fname.endswith(".html"):
            continue
        date_str = fname[:-5]
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            continue
        if date_str < cutoff_str:
            try:
                os.remove(os.path.join(DAILY_DIR, fname))
                removed.append(date_str)
                print(f"清理过期日报: {date_str}")
            except Exception:
                pass

    if removed:
        index = load_daily_index()
        index["dates"] = [d for d in index["dates"] if d["date"] not in removed]
        save_daily_index(index)

    return removed


def backfill_missing_days(days=7):
    """批量补全最近 N 天缺失的日报页面"""
    cst_tz = timezone(timedelta(hours=8))
    now_cst = datetime.now(cst_tz)

    data_path = os.path.join(BASE_DIR, "data.json")
    if not os.path.exists(data_path):
        print("data.json 不存在")
        return

    with open(data_path, "r", encoding="utf-8") as f:
        market_data = json.load(f)

    existing_dates = set(get_existing_dates())
    generated = []

    for i in range(days, 0, -1):
        date = now_cst - timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        if date_str in existing_dates:
            continue

        # 尝试加载该日期的快照，没有就用当前 data.json
        snapshot = load_daily_snapshot(date_str)
        data = snapshot if snapshot else market_data

        all_dates = sorted(set(existing_dates | {date_str}))
        try:
            idx = all_dates.index(date_str)
        except ValueError:
            idx = len(all_dates) - 1
        prev = all_dates[idx - 1] if idx > 0 else None
        nxt = all_dates[idx + 1] if idx < len(all_dates) - 1 else None

        ok = generate_for_date(date_str, data, prev, nxt)
        if ok:
            existing_dates.add(date_str)
            generated.append(date_str)

    if generated:
        print(f"补全了 {len(generated)} 个缺失日报: {generated}")
        all_final = sorted(existing_dates)
        update_sitemap_daily(all_final)
        update_homepage_recent_section(all_final)
        generate_rss_feed()
        submit_indexnow([f"{SITE_URL}/daily/{d}" for d in generated])
    else:
        print("没有缺失的日报需要补全")


def main():
    """主入口：生成"前一日"快照（用于 GitHub Actions 0:00 CST 定时触发）"""
    # 命令行参数: --backfill N 批量补全最近N天
    if len(sys.argv) > 1 and sys.argv[1] == "--backfill":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
        backfill_missing_days(days)
        return

    cst_tz = timezone(timedelta(hours=8))
    now_cst = datetime.now(cst_tz)
    yesterday_cst = now_cst - timedelta(days=1)
    target_date = yesterday_cst.strftime("%Y-%m-%d")

    print(f"=== 每日异动汇总生成器启动 ===")
    print(f"当前北京时间: {now_cst.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"目标日期（前一日）: {target_date}")

    data_path = os.path.join(BASE_DIR, "data.json")
    if not os.path.exists(data_path):
        print("data.json 不存在，请先运行 generate_data.py")
        return

    with open(data_path, "r", encoding="utf-8") as f:
        market_data = json.load(f)

    print(f"加载市场数据: {market_data.get('totalPairs', 0)} 交易对, 时间戳: {market_data.get('timestamp', 'unknown')}")

    # 保存数据快照
    save_daily_snapshot(target_date, market_data)

    existing_dates = get_existing_dates()
    all_dates = sorted(set(existing_dates + [target_date]))
    try:
        idx = all_dates.index(target_date)
    except ValueError:
        idx = len(all_dates) - 1
    prev_date = all_dates[idx - 1] if idx > 0 else None
    next_date = all_dates[idx + 1] if idx < len(all_dates) - 1 else None

    success = generate_for_date(target_date, market_data, prev_date, next_date)
    if not success:
        print(f"生成 {target_date} 日报失败")
        return

    removed = cleanup_old_pages()
    final_dates = [d for d in all_dates if d not in removed]
    update_sitemap_daily(final_dates)
    update_homepage_recent_section(final_dates)
    generate_rss_feed()
    submit_indexnow([f"{SITE_URL}/daily/{target_date}"])
    ping_google_sitemap()

    print(f"=== 完成: /daily/{target_date} 已生成 ===")


if __name__ == "__main__":
    main()

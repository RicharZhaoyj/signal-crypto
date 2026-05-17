// api/update.js — Vercel Cron Job: 每60分钟拉取OKX数据生成HTML
// 由 vercel.json 中的 crons 配置触发
// 通过 GitHub API 提交更新到仓库，Vercel 自动重新部署

const GITHUB_TOKEN = process.env.GITHUB_TOKEN;
const REPO = "RicharZhaoyj/signal-crypto";
const BRANCH = "main";

export default async function handler(req, res) {
  // Vercel Cron 会发 GET 请求
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  console.log("[Cron] 开始拉取OKX数据...");
  
  try {
    // 1. 拉取 OKX 数据
    const okxRes = await fetch("https://www.okx.com/api/v5/market/tickers?instType=SPOT", {
      signal: AbortSignal.timeout(15000)
    });
    const okxData = await okxRes.json();
    
    if (okxData.code !== "0") {
      throw new Error(`OKX API error: ${okxData.code}`);
    }

    const tickers = okxData.data
      .filter(t => t.instId.endsWith("USDT"))
      .sort((a, b) => parseFloat(b.volCcy24h || 0) - parseFloat(a.volCcy24h || 0));

    console.log(`[Cron] 获取 ${tickers.length} 个USDT交易对`);

    // 2. 分析数据
    const analysis = analyze(tickers);
    
    // 3. 生成 HTML
    const html = generateHTML(analysis);
    
    // 4. 通过 GitHub API 提交更新
    if (GITHUB_TOKEN) {
      await commitToGitHub(html, analysis);
      console.log("[Cron] GitHub 提交成功");
    } else {
      console.log("[Cron] 无 GITHUB_TOKEN，跳过 GitHub 提交");
    }

    return res.status(200).json({
      success: true,
      pairs: tickers.length,
      timestamp: new Date().toISOString(),
      summary: {
        btc: analysis.btc ? `${fmtPrice(analysis.btc.price)} (${analysis.btc.change24h}%)` : null,
        eth: analysis.eth ? `${fmtPrice(analysis.eth.price)} (${analysis.eth.change24h}%)` : null,
        up: analysis.upCount,
        down: analysis.downCount,
        volatile: analysis.volatile.length,
        sideways: analysis.sideways.length,
      }
    });
    
  } catch (err) {
    console.error("[Cron] 失败:", err.message);
    return res.status(500).json({ error: err.message });
  }
}

// ===== 分析逻辑 =====
function analyze(tickers) {
  const result = {
    timestamp: new Date().toISOString(),
    totalPairs: tickers.length,
    upCount: 0,
    downCount: 0,
    totalVolume: 0,
    btc: null,
    eth: null,
    volatile: [],
    sideways: [],
    topVolume: [],
    sentiment: "neutral"
  };

  for (const t of tickers) {
    const last = parseFloat(t.last || 0);
    const open24 = parseFloat(t.open24h || 0);
    const vol = parseFloat(t.volCcy24h || 0);
    const high = parseFloat(t.high24h || 0);
    const low = parseFloat(t.low24h || 0);
    const change24h = open24 ? Math.round((last - open24) / open24 * 10000) / 100 : 0;
    const volatility = low ? Math.round((high - low) / low * 10000) / 100 : 0;

    if (change24h > 0) result.upCount++;
    else if (change24h < 0) result.downCount++;
    result.totalVolume += vol;

    if (t.instId === "BTC-USDT") result.btc = { price: last, change24h, volume: vol, high, low };
    if (t.instId === "ETH-USDT") result.eth = { price: last, change24h, volume: vol, high, low };

    if (Math.abs(change24h) >= 5) {
      result.volatile.push({ symbol: t.instId, price: last, change: change24h, volume: vol });
    }

    if (volatility < 5 && vol > 500000) {
      result.sideways.push({ symbol: t.instId, price: last, volatility, change: change24h, volume: vol });
    }

    result.topVolume.push({ symbol: t.instId, price: last, change: change24h, volume: vol });
  }

  result.volatile.sort((a, b) => Math.abs(b.change) - Math.abs(a.change));
  result.sideways.sort((a, b) => b.volume - a.volume);
  result.topVolume.sort((a, b) => b.volume - a.volume);

  const upPct = result.totalPairs ? Math.round(result.upCount / result.totalPairs * 100) : 0;
  result.sentiment = upPct > 60 ? "bullish" : upPct < 40 ? "bearish" : "neutral";

  return result;
}

// ===== 格式化 =====
function fmtPrice(p) {
  if (p == null) return "$0";
  if (p >= 1000) return `$${p.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
  if (p >= 1) return `$${p.toFixed(4)}`;
  if (p >= 0.01) return `$${p.toFixed(6)}`;
  return `$${p.toFixed(8)}`;
}

function fmtVol(v) {
  if (v >= 1e8) return `$${(v / 1e8).toFixed(2)}B`;
  if (v >= 1e4) return `$${(v / 1e4).toFixed(2)}K`;
  return `$${v.toLocaleString('en-US')}`;
}

function chSign(v) { return v >= 0 ? '+' : ''; }
function chColor(v) { return v >= 0 ? '#ff4d4f' : '#52c41a'; }

// ===== HTML 生成（复制自 crypto_analysis_html.py 的样式）=====
function generateHTML(data) {
  const now = new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' });

  // BTC/ETH 卡片
  const btcCard = data.btc ? `
    <div class="coin-card">
      <div class="coin-name">₿ BTC</div>
      <div class="coin-price">${fmtPrice(data.btc.price)}</div>
      <div class="coin-change" style="color:${chColor(data.btc.change24h)}">${chSign(data.btc.change24h)}${data.btc.change24h}%</div>
      <div class="coin-vol">24h量 ${fmtVol(data.btc.volume)}</div>
    </div>` : '';

  const ethCard = data.eth ? `
    <div class="coin-card">
      <div class="coin-name">⟠ ETH</div>
      <div class="coin-price">${fmtPrice(data.eth.price)}</div>
      <div class="coin-change" style="color:${chColor(data.eth.change24h)}">${chSign(data.eth.change24h)}${data.eth.change24h}%</div>
      <div class="coin-vol">24h量 ${fmtVol(data.eth.volume)}</div>
    </div>` : '';

  // 情绪
  const sentimentIcon = data.sentiment === 'bullish' ? '🟢 乐观' : data.sentiment === 'bearish' ? '🔴 悲观' : '🟡 中性';
  const sentimentColor = data.sentiment === 'bullish' ? '#52c41a' : data.sentiment === 'bearish' ? '#ff4d4f' : '#ffc107';
  const upPct = data.totalPairs ? Math.round(data.upCount / data.totalPairs * 100) : 0;
  const dnPct = data.totalPairs ? Math.round(data.downCount / data.totalPairs * 100) : 0;

  // 异动表格
  let vRows = '';
  data.volatile.slice(0, 15).forEach((c, i) => {
    const color = chColor(c.change);
    vRows += `<tr><td>${i+1}</td><td class="sym">${c.symbol}</td><td>${fmtPrice(c.price)}</td><td style="color:${color};font-weight:bold;">${chSign(c.change)}${c.change}%</td><td>${fmtVol(c.volume)}</td></tr>`;
  });
  if (!vRows) vRows = '<tr><td colspan="5" style="text-align:center;color:#666;">暂无数据</td></tr>';

  // 横盘表格
  let sRows = '';
  data.sideways.slice(0, 10).forEach((c, i) => {
    const color = chColor(c.change);
    sRows += `<tr><td>${i+1}</td><td class="sym">${c.symbol}</td><td>${fmtPrice(c.price)}</td><td>${c.volatility}%</td><td style="color:${color};font-weight:bold;">${chSign(c.change)}${c.change}%</td><td>${fmtVol(c.volume)}</td></tr>`;
  });
  if (!sRows) sRows = '<tr><td colspan="6" style="text-align:center;color:#666;">暂无数据</td></tr>';

  // 成交量 Top 10
  let tRows = '';
  data.topVolume.slice(0, 10).forEach((c, i) => {
    const color = chColor(c.change);
    tRows += `<tr><td>${i+1}</td><td class="sym">${c.symbol}</td><td>${fmtPrice(c.price)}</td><td style="color:${color};">${chSign(c.change)}${c.change}%</td><td>${fmtVol(c.volume)}</td></tr>`;
  });

  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Signal · 加密货币分析</title>
<meta name="description" content="智能识别异动品种与横盘启动机会，数据来自 OKX">
<style>
*{margin:0;padding:0;box-sizing:border-box;}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,"Noto Sans SC",sans-serif;background:linear-gradient(135deg,#0f0c29 0%,#1a1a3e 40%,#24243e 100%);color:#e0e0e0;min-height:100vh;padding:20px;}
.container{max-width:1200px;margin:0 auto;}
header{text-align:center;padding:50px 20px 30px;}
h1{font-size:2.2em;background:linear-gradient(90deg,#667eea,#764ba2);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:8px;}
.subtitle{color:#aaa;font-size:1em;margin-bottom:20px;}
.update-time{display:inline-block;background:rgba(255,255,255,0.08);padding:8px 20px;border-radius:20px;font-size:0.85em;color:#aaa;}
.top-coins{display:flex;gap:20px;justify-content:center;margin:25px 0;flex-wrap:wrap;}
.coin-card{background:rgba(255,255,255,0.06);backdrop-filter:blur(8px);border:1px solid rgba(255,255,255,0.08);border-radius:16px;padding:22px 32px;min-width:200px;text-align:center;}
.coin-name{font-size:0.9em;color:#888;margin-bottom:6px;}
.coin-price{font-size:1.6em;font-weight:700;color:#fff;}
.coin-change{font-size:1.1em;font-weight:600;margin:4px 0;}
.coin-vol{font-size:0.8em;color:#888;}
.overview-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:15px;margin-bottom:30px;}
.ov-item{background:rgba(255,255,255,0.05);border-radius:12px;padding:18px;text-align:center;}
.ov-label{font-size:0.8em;color:#888;margin-bottom:6px;}
.ov-value{font-size:1.4em;font-weight:700;}
.section{background:rgba(255,255,255,0.04);backdrop-filter:blur(10px);border:1px solid rgba(255,255,255,0.06);border-radius:16px;padding:25px;margin-bottom:25px;}
h2{font-size:1.4em;margin-bottom:18px;padding-bottom:10px;border-bottom:1px solid rgba(255,255,255,0.08);}
.table-wrap{overflow-x:auto;}
table{width:100%;border-collapse:collapse;font-size:0.9em;}
th{background:rgba(255,255,255,0.06);padding:10px 12px;text-align:left;font-weight:600;color:#999;font-size:0.85em;white-space:nowrap;}
td{padding:10px 12px;border-bottom:1px solid rgba(255,255,255,0.04);white-space:nowrap;}
tr:hover td{background:rgba(255,255,255,0.03);}
.sym{font-weight:500;color:#fff;}
.promo{background:linear-gradient(135deg,rgba(102,126,234,0.12),rgba(118,75,162,0.12));border:1px solid rgba(102,126,234,0.2);border-radius:16px;padding:30px;margin-bottom:25px;text-align:center;}
.promo h3{font-size:1.2em;margin-bottom:10px;color:#fff;}
.promo p{color:#aaa;font-size:0.9em;margin-bottom:15px;}
.promo-btn{display:inline-block;padding:10px 24px;border-radius:25px;background:rgba(102,126,234,0.2);color:#fff;text-decoration:none;font-size:0.9em;border:1px solid rgba(102,126,234,0.3);margin:0 6px;}
.disclaimer{background:rgba(255,193,7,0.08);border-left:3px solid #ffc107;padding:14px 18px;border-radius:8px;font-size:0.85em;color:#bbb;margin-bottom:25px;}
footer{text-align:center;padding:30px;color:#555;font-size:0.8em;}
.badge{display:inline-block;padding:2px 10px;border-radius:10px;font-size:0.75em;font-weight:600;}
.badge-up{background:rgba(82,196,26,0.15);color:#52c41a;}
.badge-dn{background:rgba(255,77,79,0.15);color:#ff4d4f;}
@media(max-width:600px){h1{font-size:1.6em;}.section{padding:16px;}th,td{padding:8px 6px;font-size:0.8em;}}
</style>
</head>
<body>
<div class="container">
<header>
<h1>📡 Signal 加密分析</h1>
<p class="subtitle">智能识别异动品种与横盘启动机会 · 数据来自 OKX · 云端自动更新</p>
<div class="update-time">⏰ ${now}</div>
</header>
<div class="top-coins">${btcCard}${ethCard}</div>
<div class="section">
<h2>📊 市场概览</h2>
<div class="overview-grid">
<div class="ov-item"><div class="ov-label">监控品种</div><div class="ov-value">${data.totalPairs}</div></div>
<div class="ov-item"><div class="ov-label">上涨</div><div class="ov-value" style="color:#52c41a;">${data.upCount} <span style="font-size:0.6em;">(${upPct}%)</span></div></div>
<div class="ov-item"><div class="ov-label">下跌</div><div class="ov-value" style="color:#ff4d4f;">${data.downCount} <span style="font-size:0.6em;">(${dnPct}%)</span></div></div>
<div class="ov-item"><div class="ov-label">24h总成交</div><div class="ov-value" style="font-size:1.1em;">${fmtVol(data.totalVolume)}</div></div>
<div class="ov-item"><div class="ov-label">市场情绪</div><div class="ov-value" style="color:${sentimentColor};font-size:1em;">${sentimentIcon}</div></div>
</div>
</div>
<div class="section">
<h2>⚡ 异动品种 (24h涨跌 ≥ ±5%)</h2>
<div class="table-wrap"><table><thead><tr><th>#</th><th>币种</th><th>价格</th><th>24h涨跌</th><th>24h成交</th></tr></thead><tbody>${vRows}</tbody></table></div>
</div>
<div class="section">
<h2>📊 横盘关注 (波动<5%·量>50万)</h2>
<div class="table-wrap"><table><thead><tr><th>#</th><th>币种</th><th>价格</th><th>波动率</th><th>24h涨跌</th><th>24h成交</th></tr></thead><tbody>${sRows}</tbody></table></div>
</div>
<div class="section">
<h2>🔥 成交量 Top 10</h2>
<div class="table-wrap"><table><thead><tr><th>#</th><th>币种</th><th>价格</th><th>24h涨跌</th><th>24h成交</th></tr></thead><tbody>${tRows}</tbody></table></div>
</div>
<div class="promo">
<h3>📡 关注 Signal 获取更多</h3>
<p>每日异动提醒 · 横盘启动提前发现 · 市场情绪追踪</p>
<p style="margin-top:12px;font-size:0.8em;color:#666;">
由 Vercel Cron 自动更新 · 无需服务器 · 永久在线
</p>
</div>
<div class="disclaimer">
<strong>⚠️ 风险提示：</strong>本分析仅供参考，不构成投资建议。加密货币风险极高，仅用闲钱参与。
</div>
<footer>
<p>Powered by <strong>Signal</strong> · 数据来源：OKX</p>
<p style="margin-top:4px;"><a href="https://signal.link.cn" style="color:#667eea;text-decoration:none;">signal.link.cn</a> · Vercel Cron 自动更新</p>
</footer>
</div>
</body>
</html>`;
}

// ===== GitHub API 提交 =====
async function commitToGitHub(html, data) {
  const now = new Date().toISOString();
  
  // 1. 获取当前 index.html 的 SHA
  const getRes = await fetch(`https://api.github.com/repos/${REPO}/contents/index.html?ref=${BRANCH}`, {
    headers: { Authorization: `Bearer ${GITHUB_TOKEN}` }
  });
  
  let sha = null;
  if (getRes.ok) {
    const fileInfo = await getRes.json();
    sha = fileInfo.sha;
  }

  // 2. 提交新内容
  const content = Buffer.from(html).toString('base64');
  const commitRes = await fetch(`https://api.github.com/repos/${REPO}/contents/index.html`, {
    method: 'PUT',
    headers: {
      Authorization: `Bearer ${GITHUB_TOKEN}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      message: `Auto update: ${now}`,
      content,
      sha,
      branch: BRANCH,
    })
  });

  if (!commitRes.ok) {
    const err = await commitRes.json().catch(() => ({}));
    throw new Error(`GitHub commit failed: ${err.message || commitRes.status}`);
  }

  // 同时更新 data.json（存原始分析数据）
  const dataContent = Buffer.from(JSON.stringify({
    timestamp: data.timestamp,
    totalPairs: data.totalPairs,
    upCount: data.upCount,
    downCount: data.downCount,
    totalVolume: data.totalVolume,
    btc: data.btc,
    eth: data.eth,
    sentiment: data.sentiment,
    volatileCount: data.volatile.length,
    sidewaysCount: data.sideways.length
  }, null, 2)).toString('base64');

  // 获取 data.json SHA
  let dataSha = null;
  const dataRes = await fetch(`https://api.github.com/repos/${REPO}/contents/data.json?ref=${BRANCH}`, {
    headers: { Authorization: `Bearer ${GITHUB_TOKEN}` }
  });
  if (dataRes.ok) {
    const d = await dataRes.json();
    dataSha = d.sha;
  }

  await fetch(`https://api.github.com/repos/${REPO}/contents/data.json`, {
    method: 'PUT',
    headers: {
      Authorization: `Bearer ${GITHUB_TOKEN}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      message: `Update data: ${now}`,
      content: dataContent,
      sha: dataSha,
      branch: BRANCH,
    })
  });
}

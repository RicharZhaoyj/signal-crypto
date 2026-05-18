export default async function handler(req, res) {
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  // 1. 拉取 OKX 数据
  const okxRes = await fetch("https://www.okx.com/api/v5/market/tickers?instType=SPOT", {
    signal: AbortSignal.timeout(15000)
  });
  const okxData = await okxRes.json();

  if (!okxData || okxData.code !== "0") {
    return res.status(502).json({ error: "OKX API failed", code: okxData?.code });
  }

  const tickers = okxData.data
    .filter(t => t.instId.endsWith("USDT"))
    .sort((a, b) => parseFloat(b.volCcy24h || 0) - parseFloat(a.volCcy24h || 0));

  // 2. 分析数据（带具体品种列表）
  const marketData = getMarketData(tickers);

  // 3. 如果有 GITHUB_TOKEN，提交更新到仓库
  const token = process.env.GITHUB_TOKEN;
  let committed = false;
  let commitErr = null;
  if (token) {
    try {
      const html = genHTML(marketData);
      await commitFile(token, "index.html", html, `Auto update: ${new Date().toISOString()}`);
      // 更新 data.json
      const dataContent = JSON.stringify({
        timestamp: marketData.timestamp,
        totalPairs: marketData.totalPairs,
        upCount: marketData.upCount,
        downCount: marketData.downCount,
        totalVolume: marketData.totalVolume,
        sentiment: marketData.sentiment,
        btc: marketData.btc,
        eth: marketData.eth,
        volatileCount: marketData.volatile.length,
        sidewaysCount: marketData.sideways.length
      }, null, 2);
      await commitFile(token, "data.json", dataContent, `Update data: ${new Date().toISOString()}`);
      committed = true;
    } catch (err) {
      commitErr = err.message;
    }
  }

  return res.status(200).json({
    success: true,
    pairs: tickers.length,
    time: new Date().toISOString(),
    btc: marketData.btc ? `${marketData.btc.price} (${marketData.btc.change24h}%)` : null,
    eth: marketData.eth ? `${marketData.eth.price} (${marketData.eth.change24h}%)` : null,
    volatile: marketData.volatile.length,
    sideways: marketData.sideways.length,
    committed,
    error: commitErr
  });
}

// ===== 分析函数：返回完整列表 =====
function getMarketData(tickers) {
  const volatile = [];
  const sideways = [];
  const topVolume = [];
  let up = 0, down = 0, totalVol = 0;
  let btc = null, eth = null;

  for (const t of tickers) {
    const last = parseFloat(t.last || 0);
    const open24 = parseFloat(t.open24h || 0);
    const vol = parseFloat(t.volCcy24h || 0);
    const high = parseFloat(t.high24h || 0);
    const low = parseFloat(t.low24h || 0);
    const ch = open24 ? Math.round((last - open24) / open24 * 10000) / 100 : 0;
    const vl = low ? Math.round((high - low) / low * 10000) / 100 : 0;

    if (ch > 0) up++; else if (ch < 0) down++;
    totalVol += vol;

    if (t.instId === "BTC-USDT") btc = { price: last, change24h: ch, volume: vol };
    if (t.instId === "ETH-USDT") eth = { price: last, change24h: ch, volume: vol };

    if (Math.abs(ch) >= 5) {
      volatile.push({ symbol: t.instId, price: last, change: ch, volume: vol });
    }

    if (vl < 5 && vol > 500000) {
      sideways.push({ symbol: t.instId, price: last, volatility: vl, change: ch, volume: vol });
    }

    topVolume.push({ symbol: t.instId, price: last, change: ch, volume: vol });
  }

  volatile.sort((a, b) => Math.abs(b.change) - Math.abs(a.change));
  sideways.sort((a, b) => b.volume - a.volume);
  topVolume.sort((a, b) => b.volume - a.volume);

  const upPct = tickers.length ? Math.round(up / tickers.length * 100) : 0;
  const sentiment = upPct > 60 ? "bullish" : upPct < 40 ? "bearish" : "neutral";

  return {
    timestamp: new Date().toISOString(),
    totalPairs: tickers.length,
    upCount: up, downCount: down, totalVolume: totalVol,
    btc, eth, sentiment, volatile, sideways, topVolume
  };
}

async function commitFile(token, path, content, message) {
  const getUrl = `https://api.github.com/repos/RicharZhaoyj/signal-crypto/contents/${path}?ref=main`;
  let sha = null;
  const getRes = await fetch(getUrl, { headers: { Authorization: `Bearer ${token}` } });
  if (getRes.ok) {
    const info = await getRes.json();
    sha = info.sha;
  }
  const buf = Buffer.from(content, 'utf-8');
  const base64 = buf.toString('base64');
  const putRes = await fetch(`https://api.github.com/repos/RicharZhaoyj/signal-crypto/contents/${path}`, {
    method: 'PUT',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, content: base64, sha, branch: 'main' })
  });
  if (!putRes.ok) {
    const err = await putRes.json().catch(() => ({}));
    throw new Error(`GitHub commit ${path} failed: ${err.message || putRes.status}`);
  }
}

// ===== 交易所返佣链接配置 =====
const AFFILIATE = {
  okx: "https://www.kxmqpwrlvjt.com/join/72697785",
  binance: "https://www.binance.com/activity/referral/offers/claim?ref=SIGNAL",
  bybit: "https://www.bybit.com/invite?ref=SIGNAL",
  bitget: "https://partner.hdmune.cn/bg/GD38XZ",
};

// ===== HTML 生成 =====
function genHTML(d) {
  const now = new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' });
  const fmtP = p => p == null ? '$0' : p >= 1000 ? `$${p.toLocaleString('en-US', {minimumFractionDigits:2,maximumFractionDigits:2})}` : p >= 1 ? `$${p.toFixed(4)}` : p >= 0.01 ? `$${p.toFixed(6)}` : `$${p.toFixed(8)}`;
  const fmtV = v => v >= 1e8 ? `$${(v/1e8).toFixed(2)}B` : v >= 1e4 ? `$${(v/1e4).toFixed(2)}K` : `$${v.toLocaleString('en-US')}`;
  const cs = v => v >= 0 ? '+' : '';
  const cc = v => v >= 0 ? '#ff4d4f' : '#52c41a';
  const upPct = d.totalPairs ? Math.round(d.upCount/d.totalPairs*100) : 0;
  const dnPct = d.totalPairs ? Math.round(d.downCount/d.totalPairs*100) : 0;
  const si = d.sentiment === 'bullish' ? '🟢 乐观' : d.sentiment === 'bearish' ? '🔴 悲观' : '🟡 中性';
  const sc = d.sentiment === 'bullish' ? '#52c41a' : d.sentiment === 'bearish' ? '#ff4d4f' : '#ffc107';

  // 异动表格行
  let vRows = '';
  d.volatile.slice(0, 15).forEach((c, i) => {
    vRows += `<tr><td>${i+1}</td><td class="sym">${c.symbol}</td><td>${fmtP(c.price)}</td><td style="color:${cc(c.change)};font-weight:bold">${cs(c.change)}${c.change}%</td><td>${fmtV(c.volume)}</td></tr>`;
  });
  if (!vRows) vRows = '<tr><td colspan="5" style="text-align:center;color:#666;">暂无数据</td></tr>';

  // 横盘表格行
  let sRows = '';
  d.sideways.slice(0, 10).forEach((c, i) => {
    sRows += `<tr><td>${i+1}</td><td class="sym">${c.symbol}</td><td>${fmtP(c.price)}</td><td>${c.volatility}%</td><td style="color:${cc(c.change)};font-weight:bold">${cs(c.change)}${c.change}%</td><td>${fmtV(c.volume)}</td></tr>`;
  });
  if (!sRows) sRows = '<tr><td colspan="6" style="text-align:center;color:#666;">暂无数据</td></tr>';

  // 成交量 Top 10
  let tRows = '';
  d.topVolume.slice(0, 10).forEach((c, i) => {
    tRows += `<tr><td>${i+1}</td><td class="sym">${c.symbol}</td><td>${fmtP(c.price)}</td><td style="color:${cc(c.change)}">${cs(c.change)}${c.change}%</td><td>${fmtV(c.volume)}</td></tr>`;
  });

  // 样式（压缩在一行）
  const style = [
    '*{margin:0;padding:0;box-sizing:border-box}',
    'body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,"Noto Sans SC",sans-serif;background:linear-gradient(135deg,#0f0c29,#1a1a3e 40%,#24243e);color:#e0e0e0;min-height:100vh;padding:20px}',
    '.container{max-width:1200px;margin:0 auto}',
    'header{text-align:center;padding:50px 20px 30px}',
    'h1{font-size:2.2em;background:linear-gradient(90deg,#667eea,#764ba2);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:8px}',
    '.subtitle{color:#aaa;font-size:1em;margin-bottom:20px}',
    '.update-time{display:inline-block;background:rgba(255,255,255,.08);padding:8px 20px;border-radius:20px;font-size:.85em;color:#aaa}',
    '.top-coins{display:flex;gap:20px;justify-content:center;margin:25px 0;flex-wrap:wrap}',
    '.coin-card{background:rgba(255,255,255,.06);backdrop-filter:blur(8px);border:1px solid rgba(255,255,255,.08);border-radius:16px;padding:22px 32px;min-width:200px;text-align:center}',
    '.coin-name{font-size:.9em;color:#888;margin-bottom:6px}',
    '.coin-price{font-size:1.6em;font-weight:700;color:#fff}',
    '.coin-change{font-size:1.1em;font-weight:600;margin:4px 0}',
    '.coin-vol{font-size:.8em;color:#888}',
    '.section{background:rgba(255,255,255,.04);backdrop-filter:blur(10px);border:1px solid rgba(255,255,255,.06);border-radius:16px;padding:25px;margin-bottom:25px}',
    'h2{font-size:1.4em;margin-bottom:18px;padding-bottom:10px;border-bottom:1px solid rgba(255,255,255,.08)}',
    '.ov-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:15px;margin-bottom:0}',
    '.ov-item{background:rgba(255,255,255,.05);border-radius:12px;padding:18px;text-align:center}',
    '.ov-label{font-size:.8em;color:#888;margin-bottom:6px}',
    '.ov-value{font-size:1.4em;font-weight:700}',
    '.table-wrap{overflow-x:auto}',
    'table{width:100%;border-collapse:collapse;font-size:.9em}',
    'th{background:rgba(255,255,255,.06);padding:10px 12px;text-align:left;font-weight:600;color:#999;font-size:.85em;white-space:nowrap}',
    'td{padding:10px 12px;border-bottom:1px solid rgba(255,255,255,.04);white-space:nowrap}',
    'tr:hover td{background:rgba(255,255,255,.03)}',
    '.sym{font-weight:500;color:#fff}',
    '.promo{background:linear-gradient(135deg,rgba(102,126,234,.12),rgba(118,75,162,.12));border:1px solid rgba(102,126,234,.2);border-radius:16px;padding:30px;margin-bottom:25px;text-align:center}',
    '.promo h3{font-size:1.2em;margin-bottom:10px;color:#fff}',
    '.disclaimer{background:rgba(255,193,7,.08);border-left:3px solid #ffc107;padding:14px 18px;border-radius:8px;font-size:.85em;color:#bbb;margin-bottom:25px}',
    'footer{text-align:center;padding:30px;color:#555;font-size:.8em}',
    'footer a{color:#667eea;text-decoration:none}',
    '.trade-btn{display:inline-block;padding:8px 18px;border-radius:20px;background:linear-gradient(90deg,#667eea,#764ba2);color:#fff;text-decoration:none;font-size:.8em;font-weight:600;margin-top:8px;transition:opacity .2s}',
    '.trade-btn:hover{opacity:.85}',
    '@media(max-width:600px){h1{font-size:1.6em}.section{padding:16px}th,td{padding:8px 6px;font-size:.8em}}'
  ].join('');

  return `<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Signal · 加密货币分析</title><style>${style}</style></head><body><div class="container">
<header><h1>📡 Signal 加密分析</h1><p class="subtitle">智能识别异动品种与横盘启动机会 · Vercel Cron 自动更新</p><div class="update-time">⏰ ${now}</div></header>
<div class="top-coins">${d.btc?'<div class=coin-card><div class=coin-name>₿ BTC</div><div class=coin-price>'+fmtP(d.btc.price)+'</div><div class=coin-change style=color:'+cc(d.btc.change24h)+'>'+cs(d.btc.change24h)+d.btc.change24h+'%</div><div class=coin-vol>24h量 '+fmtV(d.btc.volume)+'</div><a class="trade-btn" href="'+AFFILIATE.okx+'" target="_blank" rel="nofollow noopener">去OKX交易 →</a></div>':''}${d.eth?'<div class=coin-card><div class=coin-name>⟠ ETH</div><div class=coin-price>'+fmtP(d.eth.price)+'</div><div class=coin-change style=color:'+cc(d.eth.change24h)+'>'+cs(d.eth.change24h)+d.eth.change24h+'%</div><div class=coin-vol>24h量 '+fmtV(d.eth.volume)+'</div><a class="trade-btn" href="'+AFFILIATE.okx+'" target="_blank" rel="nofollow noopener">去OKX交易 →</a></div>':''}</div>
<div class=section><h2>📊 市场概览</h2><div class=ov-grid><div class=ov-item><div class=ov-label>监控品种</div><div class=ov-value>${d.totalPairs}</div></div><div class=ov-item><div class=ov-label>上涨</div><div class=ov-value style=color:#52c41a>${d.upCount} <span style=font-size:.6em>(${upPct}%)</span></div></div><div class=ov-item><div class=ov-label>下跌</div><div class=ov-value style=color:#ff4d4f>${d.downCount} <span style=font-size:.6em>(${dnPct}%)</span></div></div><div class=ov-item><div class=ov-label>24h总成交</div><div class=ov-value>${fmtV(d.totalVolume)}</div></div><div class=ov-item><div class=ov-label>市场情绪</div><div class=ov-value style=color:${sc};font-size:1em>${si}</div></div></div></div>
<div class=section><h2>⚡ 异动品种 (24h涨跌 ≥ ±5%) — ${d.volatile.length} 个</h2><div class=table-wrap><table><thead><tr><th>#</th><th>币种</th><th>价格</th><th>24h涨跌</th><th>24h成交</th></tr></thead><tbody>${vRows}</tbody></table></div></div>
<div class=section><h2>📊 横盘关注 (波动<5%·量>50万) — ${d.sideways.length} 个</h2><div class=table-wrap><table><thead><tr><th>#</th><th>币种</th><th>价格</th><th>波动率</th><th>24h涨跌</th><th>24h成交</th></tr></thead><tbody>${sRows}</tbody></table></div></div>
<div class=section><h2>🔥 成交量 Top 10</h2><div class=table-wrap><table><thead><tr><th>#</th><th>币种</th><th>价格</th><th>24h涨跌</th><th>24h成交</th></tr></thead><tbody>${tRows}</tbody></table></div></div>
<div class="promo"><h3>💰 推荐交易所（返佣支持本站运营）</h3><p>通过以下链接注册交易，你将获得手续费折扣，本站也能获得返佣支持</p><div style="display:flex;gap:10px;justify-content:center;flex-wrap:wrap;margin-top:12px"><a class="trade-btn" href="${AFFILIATE.okx}" target="_blank" rel="nofollow noopener" style="padding:10px 24px;font-size:.9em">OKX 注册 → 享返佣</a><a class="trade-btn" href="${AFFILIATE.bitget}" target="_blank" rel="nofollow noopener" style="padding:10px 24px;font-size:.9em">Bitget 注册 → 享返佣</a><a class="trade-btn" href="${AFFILIATE.binance}" target="_blank" rel="nofollow noopener" style="padding:10px 24px;font-size:.9em">Binance 注册</a></div></div>
<div class=disclaimer><strong>⚠️ 风险提示：</strong>本分析仅供参考，不构成投资建议。加密货币风险极高，仅用闲钱参与。</div>
<footer><p>Powered by <strong>Signal</strong> · 数据来源: OKX</p><p style=margin-top:4px><a href=https://signal.link.cn>signal.link.cn</a> · Vercel Cron 自动更新</p></footer>
</div></body></html>`;
}

// /api/daily-report.js — 生成并发送每日行情日报
// 由 GitHub Actions 每天早上 8:00 触发
// 需要 Vercel 环境变量: RESEND_API_KEY, FROM_EMAIL

const GITHUB_TOKEN = process.env.GITHUB_TOKEN;
const RESEND_API_KEY = process.env.RESEND_API_KEY || process.env.RESEND_TOKEN;
const FROM_EMAIL = process.env.FROM_EMAIL || 'daily@signal.link.cn';
const REPO = "RicharZhaoyj/signal-crypto";
const BRANCH = "main";

export default async function handler(req, res) {
  // 只接受 GET（Cron 触发）
  if (req.method !== 'GET') {
    return res.status(405).json({ success: false, error: 'Method not allowed' });
  }

  try {
    // 1. 获取最新行情
    const okxRes = await fetch("https://www.okx.com/api/v5/market/tickers?instType=SPOT", {
      signal: AbortSignal.timeout(15000)
    });
    const okxData = await okxRes.json();
    if (!okxData || okxData.code !== "0") {
      throw new Error(`OKX API error: ${okxData?.code}`);
    }

    const tickers = okxData.data.filter(t => t.instId.endsWith("USDT"));
    const data = analyze(tickers);

    // 2. 生成日报 HTML
    const htmlContent = generateDailyHTML(data);
    const textContent = generateDailyText(data);

    // 3. 获取订阅列表
    let subscribers = [];
    const getRes = await fetch(
      `https://api.github.com/repos/${REPO}/contents/subscribers.json?ref=${BRANCH}`,
      { headers: { Authorization: `Bearer ${GITHUB_TOKEN}` } }
    );
    if (getRes.ok) {
      const fileInfo = await getRes.json();
      const content = Buffer.from(fileInfo.content, 'base64').toString('utf-8');
      subscribers = JSON.parse(content).filter(s => s.active);
    }

    if (subscribers.length === 0) {
      return res.status(200).json({ success: true, sent: 0, message: '暂无订阅用户' });
    }

    // 4. 发送邮件
    const sent = [];
    const failed = [];

    for (const sub of subscribers) {
      try {
        const emailRes = await fetch('https://api.resend.com/emails', {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${RESEND_API_KEY}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            from: `Signal 加密分析 <${FROM_EMAIL}>`,
            to: [sub.email],
            subject: `📡 Signal 加密日报 | ${new Date().toLocaleDateString('zh-CN')}`,
            html: htmlContent,
            text: textContent,
          })
        });
        if (emailRes.ok) {
          sent.push(sub.email);
        } else {
          const err = await emailRes.json().catch(() => ({}));
          failed.push({ email: sub.email, error: err.message || emailRes.status });
        }
      } catch (e) {
        failed.push({ email: sub.email, error: e.message });
      }
    }

    return res.status(200).json({
      success: true,
      date: new Date().toISOString(),
      subscribers: subscribers.length,
      sent: sent.length,
      failed: failed.length,
      errors: failed.slice(0, 5)
    });

  } catch (err) {
    console.error('Daily report error:', err.message);
    return res.status(500).json({ success: false, error: err.message });
  }
}

// ===== 分析函数 =====
function analyze(tickers) {
  const volatile = [], sideways = [], topVolume = [];
  let up = 0, down = 0, totalVol = 0, btc = null, eth = null;

  for (const t of tickers) {
    const last = parseFloat(t.last || 0), open24 = parseFloat(t.open24h || 0);
    const vol = parseFloat(t.volCcy24h || 0), high = parseFloat(t.high24h || 0), low = parseFloat(t.low24h || 0);
    const ch = open24 ? Math.round((last - open24) / open24 * 10000) / 100 : 0;
    const vl = low ? Math.round((high - low) / low * 10000) / 100 : 0;
    if (ch > 0) up++; else if (ch < 0) down++;
    totalVol += vol;
    if (t.instId === "BTC-USDT") btc = { price: last, change24h: ch, volume: vol };
    if (t.instId === "ETH-USDT") eth = { price: last, change24h: ch, volume: vol };
    if (Math.abs(ch) >= 5) volatile.push({ symbol: t.instId, price: last, change: ch, volume: vol });
    if (vl < 5 && vol > 500000) sideways.push({ symbol: t.instId, price: last, volatility: vl, change: ch, volume: vol });
    topVolume.push({ symbol: t.instId, volume: vol, price: last, change: ch });
  }
  volatile.sort((a, b) => Math.abs(b.change) - Math.abs(a.change));
  sideways.sort((a, b) => b.volume - a.volume);
  topVolume.sort((a, b) => b.volume - a.volume);

  const upPct = tickers.length ? Math.round(up / tickers.length * 100) : 0;
  return { timestamp: new Date().toISOString(), totalPairs: tickers.length, upCount: up, downCount: down,
    totalVolume: totalVol, btc, eth, sentiment: upPct > 60 ? 'bullish' : upPct < 40 ? 'bearish' : 'neutral',
    volatile, sideways, topVolume };
}

function fmtP(p) {
  if (p == null) return '$0';
  if (p >= 1000) return `$${p.toLocaleString('en-US', {minimumFractionDigits:2,maximumFractionDigits:2})}`;
  if (p >= 1) return `$${p.toFixed(4)}`;
  return `$${p.toFixed(6)}`;
}
function fmtV(v) {
  if (v >= 1e8) return `$${(v/1e8).toFixed(2)}B`;
  if (v >= 1e4) return `$${(v/1e4).toFixed(2)}K`;
  return `$${v.toLocaleString('en-US')}`;
}

function generateDailyHTML(d) {
  const date = new Date().toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' });
  const sentimentEmoji = d.sentiment === 'bullish' ? '🟢' : d.sentiment === 'bearish' ? '🔴' : '🟡';
  
  let volatileRows = '';
  d.volatile.slice(0, 8).forEach(c => {
    volatileRows += `<tr><td style="padding:6px 10px;border-bottom:1px solid #eee">${c.symbol}</td><td style="padding:6px 10px;border-bottom:1px solid #eee">${fmtP(c.price)}</td><td style="padding:6px 10px;border-bottom:1px solid #eee;color:${c.change>=0?'#e74c3c':'#27ae93'};font-weight:bold">${c.change>=0?'+':''}${c.change}%</td></tr>`;
  });

  let sidewaysRows = '';
  d.sideways.slice(0, 5).forEach(c => {
    sidewaysRows += `<tr><td style="padding:6px 10px;border-bottom:1px solid #eee">${c.symbol}</td><td style="padding:6px 10px;border-bottom:1px solid #eee">${fmtP(c.price)}</td><td style="padding:6px 10px;border-bottom:1px solid #eee">${c.volatility}%</td></tr>`;
  });

  return `
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f5f5f5;margin:0;padding:20px">
<div style="max-width:600px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden">
<div style="background:linear-gradient(135deg,#667eea,#764ba2);padding:30px;text-align:center;color:#fff">
<h1 style="margin:0;font-size:24px">📡 Signal 加密日报</h1>
<p style="margin:8px 0 0;opacity:.9">${date}</p>
</div>
<div style="padding:24px">
<div style="display:flex;gap:12px;margin-bottom:20px">
${d.btc?`<div style="flex:1;background:#f8f9fa;border-radius:10px;padding:16px;text-align:center"><div style="font-size:13px;color:#888">BTC</div><div style="font-size:20px;font-weight:700;margin:4px 0">${fmtP(d.btc.price)}</div><div style="font-size:14px;color:${d.btc.change24h>=0?'#e74c3c':'#27ae93'}">${d.btc.change24h>=0?'+':''}${d.btc.change24h}%</div></div>`:''}
${d.eth?`<div style="flex:1;background:#f8f9fa;border-radius:10px;padding:16px;text-align:center"><div style="font-size:13px;color:#888">ETH</div><div style="font-size:20px;font-weight:700;margin:4px 0">${fmtP(d.eth.price)}</div><div style="font-size:14px;color:${d.eth.change24h>=0?'#e74c3c':'#27ae93'}">${d.eth.change24h>=0?'+':''}${d.eth.change24h}%</div></div>`:''}
</div>
<div style="background:#f8f9fa;border-radius:10px;padding:16px;margin-bottom:20px">
<table style="width:100%;font-size:14px">
<tr><td style="padding:4px 0;color:#888">监控品种</td><td style="padding:4px 0;font-weight:600">${d.totalPairs}</td><td style="padding:4px 0;color:#888">涨/跌</td><td style="padding:4px 0;font-weight:600"><span style="color:#e74c3c">↑${d.upCount}</span> / <span style="color:#27ae93">↓${d.downCount}</span></td></tr>
<tr><td style="padding:4px 0;color:#888">24h成交</td><td style="padding:4px 0;font-weight:600">${fmtV(d.totalVolume)}</td><td style="padding:4px 0;color:#888">情绪</td><td style="padding:4px 0;font-weight:600">${sentimentEmoji} ${d.sentiment==='bullish'?'乐观':d.sentiment==='bearish'?'悲观':'中性'}</td></tr>
</table>
</div>
${volatileRows ? `<h3 style="font-size:16px;margin:0 0 10px">⚡ 异动品种 Top 8</h3><table style="width:100%;font-size:13px;border-collapse:collapse;margin-bottom:20px"><thead><tr style="background:#f0f0f0"><th style="padding:6px 10px;text-align:left">币种</th><th style="padding:6px 10px;text-align:left">价格</th><th style="padding:6px 10px;text-align:left">24h涨跌</th></tr></thead><tbody>${volatileRows}</tbody></table>`:''}
${sidewaysRows ? `<h3 style="font-size:16px;margin:0 0 10px">📊 横盘关注</h3><table style="width:100%;font-size:13px;border-collapse:collapse;margin-bottom:20px"><thead><tr style="background:#f0f0f0"><th style="padding:6px 10px;text-align:left">币种</th><th style="padding:6px 10px;text-align:left">价格</th><th style="padding:6px 10px;text-align:left">波动率</th></tr></thead><tbody>${sidewaysRows}</tbody></table>`:''}
<div style="text-align:center;margin-top:20px;padding-top:16px;border-top:1px solid #eee">
<p style="font-size:12px;color:#999">查看完整数据: <a href="https://signal.link.cn" style="color:#667eea">signal.link.cn</a></p>
<p style="font-size:11px;color:#bbb">如果不想再接收日报，回复此邮件即可退订</p>
</div>
</div></div></body></html>`;
}

function generateDailyText(d) {
  const date = new Date().toLocaleDateString('zh-CN');
  const lines = [
    `📡 Signal 加密日报 - ${date}`,
    `=============================`,
    ``,
    `BTC: ${d.btc ? `${fmtP(d.btc.price)} (${d.btc.change24h>=0?'+':''}${d.btc.change24h}%)` : 'N/A'}`,
    `ETH: ${d.eth ? `${fmtP(d.eth.price)} (${d.eth.change24h>=0?'+':''}${d.eth.change24h}%)` : 'N/A'}`,
    ``,
    `监控: ${d.totalPairs} | ↑${d.upCount} ↓${d.downCount}`,
    `成交: ${fmtV(d.totalVolume)} | 情绪: ${d.sentiment}`,
    ``,
    `⚡ 异动 ${d.volatile.length} 个`,
    ...d.volatile.slice(0, 8).map(c => `  ${c.symbol}: ${fmtP(c.price)} (${c.change>=0?'+':''}${c.change}%)`),
    ``,
    `📊 横盘 ${d.sideways.length} 个`,
    ...d.sideways.slice(0, 5).map(c => `  ${c.symbol}: ${fmtP(c.price)} | 波动: ${c.volatility}%`),
    ``,
    `完整数据: https://signal.link.cn`,
    `退订: 回复此邮件`
  ];
  return lines.join('\n');
}

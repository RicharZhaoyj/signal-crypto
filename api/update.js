export default async function handler(req, res) {
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    // 1. 拉取 OKX 数据
    const okxRes = await fetch("https://www.okx.com/api/v5/market/tickers?instType=SPOT", {
      signal: AbortSignal.timeout(15000)
    });
    const okxData = await okxRes.json();

    if (!okxData || okxData.code !== "0") {
      return res.status(502).json({ 
        success: false, 
        error: "OKX API failed", 
        code: okxData?.code 
      });
    }

    const tickers = okxData.data
      .filter(t => t.instId.endsWith("USDT"))
      .sort((a, b) => parseFloat(b.volCcy24h || 0) - parseFloat(a.volCcy24h || 0));

    // 2. 分析数据
    const marketData = getMarketData(tickers);

    // 3. 生成轻量 data.json
    const dataContent = JSON.stringify({
      timestamp: new Date().toISOString(),
      totalPairs: marketData.totalPairs,
      upCount: marketData.upCount,
      downCount: marketData.downCount,
      totalVolume: marketData.totalVolume,
      sentiment: marketData.sentiment,
      btc: marketData.btc,
      eth: marketData.eth,
      volatile: marketData.volatile,
      sideways: marketData.sideways,
      topVolume: marketData.topVolume
    }, null, 2);

    // 4. 提交到 GitHub（如果有 Token）
    const token = process.env.GITHUB_TOKEN;
    let committed = false;
    let commitError = null;

    if (token) {
      try {
        await commitFile(token, "data.json", dataContent, `Auto update: ${new Date().toISOString()}`);
        committed = true;
      } catch (err) {
        commitError = err.message;
        console.error("GitHub commit failed:", err);
      }
    }

    return res.status(200).json({
      success: true,
      pairs: tickers.length,
      time: new Date().toISOString(),
      committed,
      commitError,
      message: committed 
        ? "数据已成功更新到 GitHub" 
        : "数据已生成，但未提交（缺少 GITHUB_TOKEN）"
    });

  } catch (error) {
    console.error("Update error:", error);
    return res.status(500).json({ 
      success: false, 
      error: error.message 
    });
  }
}

// ===== 数据分析 =====
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

    const change = open24 ? Math.round((last - open24) / open24 * 10000) / 100 : 0;
    const volatility = low ? Math.round((high - low) / low * 10000) / 100 : 0;

    totalVol += vol;

    if (t.instId === 'BTC-USDT') {
      btc = { price: last, change24h: change, volume: vol };
    }
    if (t.instId === 'ETH-USDT') {
      eth = { price: last, change24h: change, volume: vol };
    }

    if (change >= 5 || change <= -5) {
      volatile.push({ symbol: t.instId, price: last, change, volume: vol });
    }

    if (volatility < 5 && vol > 500000 && !t.instId.includes('USD')) {
      sideways.push({ symbol: t.instId, price: last, volatility, change, volume: vol });
    }

    if (topVolume.length < 10) {
      topVolume.push({ symbol: t.instId, price: last, change, volume: vol });
    }

    if (change > 0) up++;
    else if (change < 0) down++;
  }

  // 排序
  volatile.sort((a, b) => Math.abs(b.change) - Math.abs(a.change));
  sideways.sort((a, b) => a.volatility - b.volatility);

  return {
    totalPairs: tickers.length,
    upCount: up,
    downCount: down,
    totalVolume: totalVol,
    sentiment: up > down * 1.5 ? 'bullish' : down > up * 1.5 ? 'bearish' : 'neutral',
    btc,
    eth,
    volatile: volatile.slice(0, 20),
    sideways: sideways.slice(0, 15),
    topVolume
  };
}

// ===== GitHub 提交 =====
async function commitFile(token, path, content, message) {
  const repo = "RicharZhaoyj/signal-crypto";
  const getUrl = `https://api.github.com/repos/${repo}/contents/${path}?ref=main`;

  let sha = null;
  const getRes = await fetch(getUrl, {
    headers: { Authorization: `Bearer ${token}` }
  });

  if (getRes.ok) {
    const info = await getRes.json();
    sha = info.sha;
  }

  const base64 = Buffer.from(content, 'utf-8').toString('base64');

  const putRes = await fetch(`https://api.github.com/repos/${repo}/contents/${path}`, {
    method: 'PUT',
    headers: { 
      Authorization: `Bearer ${token}`, 
      'Content-Type': 'application/json' 
    },
    body: JSON.stringify({ 
      message, 
      content: base64, 
      sha, 
      branch: 'main' 
    })
  });

  if (!putRes.ok) {
    const err = await putRes.json().catch(() => ({}));
    throw new Error(`GitHub commit failed: ${err.message || putRes.status}`);
  }
}
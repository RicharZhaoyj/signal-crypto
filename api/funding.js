// Vercel Serverless Function - 资金费率代理
// 支持 OKX / Binance / Bitget，避免浏览器 CORS 问题

export default async function handler(req, res) {
  const { exchange = 'okx' } = req.query;

  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Cache-Control', 's-maxage=60'); // 缓存 60 秒

  try {
    let rates = [];

    if (exchange === 'okx') {
      const r = await fetch('https://www.okx.com/api/v5/public/funding-rate?instType=SWAP');
      const data = await r.json();
      if (data.code === '0') {
        rates = data.data.map(item => ({
          symbol: item.instId.replace('-SWAP', '').replace('-USDT', ''),
          fundingRate: parseFloat(item.fundingRate) * 100,
          ts: item.fundingTime
        })).filter(r => !isNaN(r.fundingRate));
      }
    } 
    else if (exchange === 'binance') {
      const r = await fetch('https://fapi.binance.com/fapi/v1/premiumIndex');
      const data = await r.json();
      rates = data.map(item => ({
        symbol: item.symbol.replace('USDT', ''),
        fundingRate: parseFloat(item.lastFundingRate) * 100,
        ts: Date.now()
      })).filter(r => !isNaN(r.fundingRate));
    } 
    else if (exchange === 'bitget') {
      // Bitget 需要先获取所有永续合约列表，再查费率（简化处理）
      const r = await fetch('https://api.bitget.com/api/mix/v1/market/tickers?productType=USDT-FUTURES');
      const data = await r.json();
      if (data.code === '00000' && data.data) {
        rates = data.data
          .filter(item => item.symbol.endsWith('USDT_UMCBL'))
          .map(item => ({
            symbol: item.symbol.replace('USDT_UMCBL', ''),
            fundingRate: parseFloat(item.fundingRate) * 100,
            ts: Date.now()
          }))
          .filter(r => !isNaN(r.fundingRate));
      }
    }

    res.status(200).json({ success: true, exchange, rates, count: rates.length });

  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
}
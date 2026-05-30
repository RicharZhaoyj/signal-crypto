// Vercel Serverless Function - 资金费率代理
// 支持 OKX / Binance

export default async function handler(req, res) {
  const { exchange = 'okx' } = req.query;

  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Cache-Control', 's-maxage=60');

  try {
    let rates = [];

    if (exchange === 'okx') {
      const r = await fetch('https://www.okx.com/api/v5/public/funding-rate?instType=SWAP', {
        headers: { 'User-Agent': 'Mozilla/5.0' }
      });
      const data = await r.json();

      if (data.code === '0' && Array.isArray(data.data)) {
        rates = data.data
          .map(item => {
            const base = item.instId ? item.instId.split('-')[0] : '';
            return {
              symbol: base,
              fundingRate: parseFloat(item.fundingRate) * 100,
              ts: item.fundingTime || Date.now()
            };
          })
          .filter(r => r.symbol && !isNaN(r.fundingRate));
      }
    } 
    else if (exchange === 'binance') {
      const r = await fetch('https://fapi.binance.com/fapi/v1/premiumIndex');
      const data = await r.json();

      // Binance 有时会返回对象而不是数组
      if (Array.isArray(data)) {
        rates = data
          .map(item => ({
            symbol: item.symbol ? item.symbol.replace('USDT', '') : '',
            fundingRate: parseFloat(item.lastFundingRate) * 100,
            ts: Date.now()
          }))
          .filter(r => r.symbol && !isNaN(r.fundingRate));
      }
    }

    res.status(200).json({ 
      success: true, 
      exchange, 
      rates, 
      count: rates.length 
    });

  } catch (error) {
    res.status(200).json({ 
      success: false, 
      exchange,
      error: error.message 
    });
  }
}
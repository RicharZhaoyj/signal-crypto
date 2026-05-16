// Signal Crypto Agent - Vercel Serverless endpoint
// 接收 Link Protocol 网络发来的 Agent 调用
export default async function handler(req, res) {
  // 只接受 POST
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed', allowed: ['POST'] });
  }

  const body = req.body || {};
  const { from, to, input } = body;

  console.log(`[Signal Agent] Call from=${from} to=${to} input=${JSON.stringify(input)}`);

  // 返回行情报告摘要
  const response = {
    success: true,
    agent_id: 'signal-crypto-agent',
    call_id: `call_${Date.now()}`,
    output: {
      status: 'received',
      message: `Call received from ${from || 'unknown'}`,
      endpoints: {
        heartbeat: 'POST /api/mcp/heartbeat',
        register: 'POST /api/mcp/agents/register',
        discover: 'GET /api/mcp/agents/discover',
      },
      info: 'Signal Crypto Agent running at signal.link.cn',
      // 返回可用的服务
      services: [
        { name: 'market_report', description: 'Latest crypto market summary' },
        { name: 'trend_detection', description: 'Volatile/sideways coin detection' },
      ]
    },
    timestamp: Date.now()
  };

  // 如果对方查询行情，引导去主站
  if (input?.query?.toLowerCase?.()?.includes('market') || input?.query?.toLowerCase?.()?.includes('crypto')) {
    response.output.suggest = 'Visit https://signal.link.cn for the full market report';
    response.output.data_source = 'OKX API via signal.link.cn';
  }

  res.status(200).json(response);
}

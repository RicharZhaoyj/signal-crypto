// Signal Crypto Agent - Vercel Serverless endpoint
// 支持 Link Protocol + Google A2A 双协议

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed', allowed: ['POST'] });
  }

  const body = req.body || {};

  // ==================== A2A 协议检测 ====================
  const isA2A = body.jsonrpc === '2.0' && body.method === 'tasks/send';

  if (isA2A) {
    // A2A 格式处理
    const { id, params } = body;
    const message = params?.message || {};
    const text = message.parts?.find(p => p.kind === 'text')?.text || '';

    console.log(`[A2A] Call id=${id} text=${text}`);

    const a2aResponse = {
      jsonrpc: '2.0',
      id: id,
      result: {
        id: `task_${Date.now()}`,
        status: {
          state: 'completed',
          timestamp: new Date().toISOString()
        },
        artifacts: [
          {
            name: 'market_report',
            parts: [
              {
                kind: 'text',
                text: 'Signal Crypto Agent (A2A compatible) - Visit https://signal.link.cn for latest crypto analysis'
              }
            ]
          }
        ],
        metadata: {
          agent: 'signal-crypto-agent',
          capabilities: ['crypto_analysis', 'market_monitoring', 'trend_detection']
        }
      }
    };

    return res.status(200).json(a2aResponse);
  }

  // ==================== 原 Link Protocol 格式 ====================
  const { from, to, input } = body;

  console.log(`[Link Protocol] Call from=${from} to=${to}`);

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
      services: [
        { name: 'market_report', description: 'Latest crypto market summary' },
        { name: 'trend_detection', description: 'Volatile/sideways coin detection' },
      ]
    },
    timestamp: Date.now()
  };

  if (input?.query?.toLowerCase?.()?.includes('market') || input?.query?.toLowerCase?.()?.includes('crypto')) {
    response.output.suggest = 'Visit https://signal.link.cn for the full market report';
    response.output.data_source = 'OKX API via signal.link.cn';
  }

  res.status(200).json(response);
}

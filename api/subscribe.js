// /api/subscribe.js — 邮箱订阅
// 订阅数据存储在 GitHub 仓库的 subscribers.json

const GITHUB_TOKEN = process.env.GITHUB_TOKEN;
const REPO = "RicharZhaoyj/signal-crypto";
const BRANCH = "main";
const SUBSCRIBERS_PATH = "subscribers.json";

export default async function handler(req, res) {
  // 只接受 POST
  if (req.method !== 'POST') {
    return res.status(405).json({ success: false, error: 'Method not allowed' });
  }

  const { email } = req.body || {};
  if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return res.status(400).json({ success: false, error: '请输入有效的邮箱地址' });
  }

  if (!GITHUB_TOKEN) {
    return res.status(500).json({ success: false, error: '服务器配置错误，请联系管理员' });
  }

  try {
    // 1. 获取当前 subscribers.json
    let subscribers = [];
    let sha = null;

    const getRes = await fetch(
      `https://api.github.com/repos/${REPO}/contents/${SUBSCRIBERS_PATH}?ref=${BRANCH}`,
      { headers: { Authorization: `Bearer ${GITHUB_TOKEN}` } }
    );

    if (getRes.ok) {
      const fileInfo = await getRes.json();
      sha = fileInfo.sha;
      const content = Buffer.from(fileInfo.content, 'base64').toString('utf-8');
      subscribers = JSON.parse(content);
    }

    // 2. 检查是否已存在
    if (subscribers.some(s => s.email === email)) {
      return res.status(200).json({ success: true, message: '该邮箱已订阅' });
    }

    // 3. 添加新订阅
    subscribers.push({
      email,
      subscribed_at: new Date().toISOString(),
      active: true
    });

    // 4. 写回 GitHub
    const updatedContent = Buffer.from(JSON.stringify(subscribers, null, 2)).toString('base64');
    const putRes = await fetch(
      `https://api.github.com/repos/${REPO}/contents/${SUBSCRIBERS_PATH}`,
      {
        method: 'PUT',
        headers: {
          Authorization: `Bearer ${GITHUB_TOKEN}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: `Subscribe: ${email}`,
          content: updatedContent,
          sha,
          branch: BRANCH,
        })
      }
    );

    if (!putRes.ok) {
      const err = await putRes.json().catch(() => ({}));
      throw new Error(err.message || 'GitHub write failed');
    }

    return res.status(200).json({ success: true, message: '订阅成功' });
  } catch (err) {
    console.error('Subscribe error:', err.message);
    return res.status(500).json({ success: false, error: '订阅失败，请稍后重试' });
  }
}

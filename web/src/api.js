export async function api(path, options = {}) {
  let response;
  try {
    response = await fetch(`/api${path}`, {
      ...options,
      headers: { 'Content-Type': 'application/json', ...options.headers },
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });
  } catch {
    throw new Error('暂时连不上本地服务。请确认 Brand Radar 服务仍在运行，再重试。');
  }
  const text = await response.text();
  let data;
  try { data = text ? JSON.parse(text) : {}; }
  catch { throw new Error('本地服务返回了无法读取的内容，请重试。'); }
  if (!response.ok) {
    const reason = data.error || data.detail || data.message;
    throw new Error(typeof reason === 'string' ? reason : reason?.message || `请求未完成（${response.status}），请重试。`);
  }
  return data;
}

export function safeUrl(value) {
  if (!value) return null;
  try {
    const url = new URL(value);
    return ['https:', 'http:'].includes(url.protocol) ? url.href : null;
  } catch { return null; }
}

export function siteName(value) {
  try { return new URL(value).hostname.replace(/^www\./, ''); }
  catch { return '用户提供的材料'; }
}

export function dateLabel(value, includeTime = false) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return value;
  return new Intl.DateTimeFormat('zh-CN', {
    ...(date.getFullYear() !== new Date().getFullYear() ? { year: 'numeric' } : {}), month: 'short', day: 'numeric', ...(includeTime ? { hour: '2-digit', minute: '2-digit' } : {}),
  }).format(date);
}

export function visibleActivity(task) {
  const activity = task?.activity || [];
  if (task?.status !== 'running') return activity;
  const latestRequest = [...(task.messages || [])].reverse().find(message => message.role === 'user');
  const startedAt = Date.parse(latestRequest?.created_at);
  if (!Number.isFinite(startedAt)) return [];
  return activity.filter(item => Date.parse(item.created_at) >= startedAt);
}

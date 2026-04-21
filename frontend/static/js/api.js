const token = () => localStorage.getItem('token');

async function apiFetch(url, options = {}) {
  const r = await fetch(url, {
    ...options,
    headers: { 'Authorization': `Bearer ${token()}`, 'Content-Type': 'application/json', ...options.headers }
  });
  if (r.status === 401) { localStorage.removeItem('token'); location.href = '/'; return; }
  return r;
}

async function apiGet(url) { return (await apiFetch(url)).json(); }
async function apiPost(url, body) { return (await apiFetch(url, { method: 'POST', body: JSON.stringify(body) })).json(); }
async function apiPut(url, body) { return (await apiFetch(url, { method: 'PUT', body: JSON.stringify(body) })).json(); }
async function apiPatch(url, body) { return (await apiFetch(url, { method: 'PATCH', body: JSON.stringify(body) })).json(); }
async function apiDelete(url) { return (await apiFetch(url, { method: 'DELETE' })).json(); }

function statusBadge(status) {
  const map = { hot: 'bg-red-100 text-red-700', warm: 'bg-yellow-100 text-yellow-700', cold: 'bg-blue-100 text-blue-700', new: 'bg-gray-100 text-gray-600', lost: 'bg-gray-200 text-gray-500' };
  const labels = { hot: 'Quente', warm: 'Morno', cold: 'Frio', new: 'Novo', lost: 'Perdido' };
  return `<span class="px-2 py-0.5 rounded-full text-xs font-medium ${map[status]||'bg-gray-100 text-gray-600'}">${labels[status]||status}</span>`;
}

function timeAgo(iso) {
  const utc = iso.endsWith('Z') ? iso : iso + 'Z';
  const diff = Math.floor((Date.now() - new Date(utc)) / 1000);
  if (diff < 0) return 'agora';
  if (diff < 60) return `${diff}s atrás`;
  if (diff < 3600) return `${Math.floor(diff/60)}min atrás`;
  if (diff < 86400) return `${Math.floor(diff/3600)}h atrás`;
  return `${Math.floor(diff/86400)}d atrás`;
}

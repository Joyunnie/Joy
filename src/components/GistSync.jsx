import { useState, useEffect, useCallback } from 'react';
import { getOverridesData, setOverridesData, getItemOrderData, setItemOrderData } from '../data/foodData';

const TOKEN_KEY = 'catfood_gist_token';
const GIST_ID_KEY = 'catfood_gist_id';
const FILENAME = 'catfood_sync_data.json';
const RECIPES_KEY = 'catfood_saved_recipes';
const INVENTORY_KEY = 'catfood_inventory';
const OMEGA3_KEY = 'catfood_omega3_custom';
const BLACKLIST_KEY = 'catfood_recommend_blacklist';

function getToken() { return localStorage.getItem(TOKEN_KEY) || ''; }
function getGistId() { return localStorage.getItem(GIST_ID_KEY) || ''; }

async function findOrCreateGist(token) {
  let gistId = getGistId();
  if (gistId) {
    try {
      const r = await fetch(`https://api.github.com/gists/${gistId}`, {
        headers: { Authorization: `token ${token}` },
      });
      if (r.ok) return gistId;
    } catch {}
    localStorage.removeItem(GIST_ID_KEY);
  }
  // Search existing gists
  const res = await fetch('https://api.github.com/gists?per_page=100', {
    headers: { Authorization: `token ${token}` },
  });
  if (!res.ok) throw new Error(`GitHub API 오류: ${res.status}`);
  const gists = await res.json();
  const existing = gists.find(g => g.files[FILENAME]);
  if (existing) {
    localStorage.setItem(GIST_ID_KEY, existing.id);
    return existing.id;
  }
  // Create new
  const createRes = await fetch('https://api.github.com/gists', {
    method: 'POST',
    headers: { Authorization: `token ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      description: '고양이 생식 레시피 동기화 데이터',
      public: false,
      files: { [FILENAME]: { content: JSON.stringify({ version: 1, lastSync: new Date().toISOString() }) } },
    }),
  });
  if (!createRes.ok) throw new Error(`Gist 생성 실패: ${createRes.status}`);
  const created = await createRes.json();
  localStorage.setItem(GIST_ID_KEY, created.id);
  return created.id;
}

function gatherLocalData() {
  let recipes = [];
  try { recipes = JSON.parse(localStorage.getItem(RECIPES_KEY)) || []; } catch {}
  let inventory = [];
  try { inventory = JSON.parse(localStorage.getItem(INVENTORY_KEY)) || []; } catch {}
  let omega3Custom = {};
  try { omega3Custom = JSON.parse(localStorage.getItem(OMEGA3_KEY)) || {}; } catch {}
  let recommendBlacklist = [];
  try { recommendBlacklist = JSON.parse(localStorage.getItem(BLACKLIST_KEY)) || []; } catch {}
  return {
    version: 1,
    lastSync: new Date().toISOString(),
    recipes,
    customFoods: getOverridesData(),
    itemOrder: getItemOrderData(),
    omega3Custom,
    inventory,
    recommendBlacklist,
  };
}

function applyRemoteData(remote) {
  if (!remote) return;
  // Merge recipes by name (remote wins if newer)
  if (remote.recipes) {
    let local = [];
    try { local = JSON.parse(localStorage.getItem(RECIPES_KEY)) || []; } catch {}
    const map = new Map(local.map(r => [r.name, r]));
    for (const r of remote.recipes) map.set(r.name, r);
    localStorage.setItem(RECIPES_KEY, JSON.stringify([...map.values()]));
  }
  if (remote.customFoods) {
    const existing = getOverridesData();
    const merged = { ...existing };
    for (const [catKey, catOv] of Object.entries(remote.customFoods)) {
      if (!merged[catKey]) { merged[catKey] = catOv; continue; }
      const m = merged[catKey];
      if (catOv.added) {
        if (!m.added) m.added = [];
        const names = new Set(m.added.map(f => f.name));
        for (const f of catOv.added) {
          if (names.has(f.name)) {
            const idx = m.added.findIndex(e => e.name === f.name);
            if (idx >= 0) m.added[idx] = f;
          } else m.added.push(f);
        }
      }
      if (catOv.modified) m.modified = { ...(m.modified || {}), ...catOv.modified };
      if (catOv.deleted) m.deleted = [...new Set([...(m.deleted || []), ...catOv.deleted])];
    }
    setOverridesData(merged);
  }
  if (remote.itemOrder) {
    setItemOrderData(remote.itemOrder);
  }
  if (remote.inventory) {
    localStorage.setItem(INVENTORY_KEY, JSON.stringify(remote.inventory));
  }
  if (remote.omega3Custom) {
    localStorage.setItem(OMEGA3_KEY, JSON.stringify(remote.omega3Custom));
  }
  if (remote.recommendBlacklist) {
    // Merge: union of local and remote
    let local = [];
    try { local = JSON.parse(localStorage.getItem(BLACKLIST_KEY)) || []; } catch {}
    const merged = [...new Set([...local, ...remote.recommendBlacklist])];
    localStorage.setItem(BLACKLIST_KEY, JSON.stringify(merged));
  }
}

export async function saveToGist(token) {
  if (!token) return;
  const gistId = await findOrCreateGist(token);
  const data = gatherLocalData();
  await fetch(`https://api.github.com/gists/${gistId}`, {
    method: 'PATCH',
    headers: { Authorization: `token ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ files: { [FILENAME]: { content: JSON.stringify(data, null, 2) } } }),
  });
}

export async function loadFromGist(token) {
  if (!token) return null;
  const gistId = await findOrCreateGist(token);
  const res = await fetch(`https://api.github.com/gists/${gistId}`, {
    headers: { Authorization: `token ${token}` },
  });
  if (!res.ok) return null;
  const gist = await res.json();
  const file = gist.files[FILENAME];
  if (!file) return null;
  return JSON.parse(file.content);
}

export default function GistSync({ onSyncComplete }) {
  const [token, setToken] = useState(getToken);
  const [inputToken, setInputToken] = useState('');
  const [connected, setConnected] = useState(!!getToken());
  const [syncing, setSyncing] = useState(false);
  const [status, setStatus] = useState('');
  const [open, setOpen] = useState(false);

  // Auto-sync on mount if token exists
  useEffect(() => {
    if (connected && token) {
      handlePull(true);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleConnect = async () => {
    const t = inputToken.trim();
    if (!t) return;
    setSyncing(true);
    setStatus('연결 중...');
    try {
      const res = await fetch('https://api.github.com/user', {
        headers: { Authorization: `token ${t}` },
      });
      if (!res.ok) throw new Error('토큰이 유효하지 않습니다');
      localStorage.setItem(TOKEN_KEY, t);
      setToken(t);
      setConnected(true);
      setInputToken('');
      // Pull from gist
      const remote = await loadFromGist(t);
      if (remote) {
        applyRemoteData(remote);
        setStatus('연결됨 - 데이터 동기화 완료');
        if (onSyncComplete) onSyncComplete();
      } else {
        // Push local data to new gist
        await saveToGist(t);
        setStatus('연결됨 - 로컬 데이터 업로드 완료');
      }
    } catch (err) {
      setStatus(`오류: ${err.message}`);
    }
    setSyncing(false);
  };

  const handleDisconnect = () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(GIST_ID_KEY);
    setToken('');
    setConnected(false);
    setStatus('');
  };

  const handlePush = async () => {
    setSyncing(true);
    setStatus('업로드 중...');
    try {
      await saveToGist(token);
      setStatus(`동기화 완료 (${new Date().toLocaleTimeString()})`);
    } catch (err) {
      setStatus(`오류: ${err.message}`);
    }
    setSyncing(false);
  };

  const handlePull = async (silent) => {
    if (!silent) { setSyncing(true); setStatus('다운로드 중...'); }
    try {
      const remote = await loadFromGist(token);
      if (remote) {
        applyRemoteData(remote);
        if (!silent) {
          setStatus(`불러오기 완료 (${new Date().toLocaleTimeString()})`);
          if (onSyncComplete) onSyncComplete();
        }
      } else {
        if (!silent) setStatus('Gist에 데이터 없음');
      }
    } catch (err) {
      if (!silent) setStatus(`오류: ${err.message}`);
    }
    if (!silent) setSyncing(false);
  };

  return (
    <div className="bg-white rounded p-1.5 shadow-sm border">
      <button onClick={() => setOpen(!open)} className="flex items-center gap-1 w-full text-left">
        <span className="text-[10px] font-bold text-gray-700">클라우드 동기화</span>
        {connected && <span className="text-[9px] text-green-600 font-semibold">연결됨</span>}
        <span className="text-[9px] text-gray-400 ml-auto">{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div className="mt-1 space-y-1">
          {!connected ? (
            <>
              <div className="text-[9px] text-gray-500">GitHub Personal Access Token (gist 권한)</div>
              <div className="flex gap-1">
                <input type="password"
                  className="flex-1 text-[10px] border border-gray-300 rounded px-1 py-0.5"
                  placeholder="ghp_..."
                  value={inputToken}
                  onChange={(e) => setInputToken(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleConnect()}
                />
                <button onClick={handleConnect} disabled={syncing}
                  className="text-[9px] px-1.5 py-0.5 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50">
                  연결
                </button>
              </div>
            </>
          ) : (
            <div className="flex gap-1 flex-wrap">
              <button onClick={handlePush} disabled={syncing}
                className="text-[9px] px-1.5 py-0.5 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50">
                업로드
              </button>
              <button onClick={() => handlePull(false)} disabled={syncing}
                className="text-[9px] px-1.5 py-0.5 bg-teal-500 text-white rounded hover:bg-teal-600 disabled:opacity-50">
                다운로드
              </button>
              <button onClick={handleDisconnect}
                className="text-[9px] px-1.5 py-0.5 bg-gray-400 text-white rounded hover:bg-gray-500">
                연결 해제
              </button>
            </div>
          )}
          {status && <div className="text-[9px] text-gray-500">{status}</div>}
        </div>
      )}
    </div>
  );
}

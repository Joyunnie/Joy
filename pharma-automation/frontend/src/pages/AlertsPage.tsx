import { useCallback, useEffect, useRef, useState } from 'react';
import { fetchAlerts, markAlertRead } from '../api/alertsApi.ts';
import type { AlertOut } from '../types/api.ts';
import Pagination from '../components/Pagination.tsx';
import EmptyState from '../components/EmptyState.tsx';
import Spinner from '../components/Spinner.tsx';
import FilterChips from '../components/FilterChips.tsx';
import Toast from '../components/Toast.tsx';
import { useToast } from '../hooks/useToast.ts';

const ALERT_TYPES = [
  { value: '', label: '전체' },
  { value: 'LOW_STOCK', label: '재고부족' },
  { value: 'NARCOTICS_LOW', label: '마약류' },
  { value: 'VISIT_APPROACHING', label: '내원예측' },
] as const;

const READ_FILTERS = [
  { value: '', label: '전체' },
  { value: 'unread', label: '안읽음' },
  { value: 'read', label: '읽음' },
] as const;

function alertIcon(type: string): string {
  switch (type) {
    case 'LOW_STOCK': return '\u26A0\uFE0F';
    case 'NARCOTICS_LOW': return '\uD83D\uDED1';
    case 'VISIT_APPROACHING': return '\uD83D\uDCC5';
    default: return '\uD83D\uDD14';
  }
}

function alertColor(type: string): string {
  switch (type) {
    case 'LOW_STOCK': return 'border-l-orange-400';
    case 'NARCOTICS_LOW': return 'border-l-red-500';
    case 'VISIT_APPROACHING': return 'border-l-blue-400';
    default: return 'border-l-gray-300';
  }
}

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return '방금';
  if (mins < 60) return `${mins}분 전`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}시간 전`;
  const days = Math.floor(hours / 24);
  return `${days}일 전`;
}

const POLL_INTERVAL_MS = 60_000;
const LIMIT = 20;

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<AlertOut[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [typeFilter, setTypeFilter] = useState('');
  const [readFilter, setReadFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const loaded = useRef(false);
  const polling = useRef(false);
  const { toasts, showToast, removeToast } = useToast();

  const loadAlerts = useCallback(async () => {
    if (polling.current) return;
    polling.current = true;
    if (!loaded.current) setLoading(true);
    try {
      const data = await fetchAlerts({
        limit: LIMIT,
        offset,
        alert_type: typeFilter || undefined,
        unread_only: readFilter === 'unread' || undefined,
        read_only: readFilter === 'read' || undefined,
      });
      setAlerts(data.alerts);
      setTotal(data.total);
    } catch {
      if (!loaded.current) showToast('알림을 불러오지 못했습니다', 'error');
    } finally {
      loaded.current = true;
      polling.current = false;
      setLoading(false);
    }
  }, [offset, typeFilter, readFilter, showToast]);

  useEffect(() => { loadAlerts(); }, [loadAlerts]);

  useEffect(() => {
    const id = setInterval(() => {
      if (!document.hidden) loadAlerts();
    }, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [loadAlerts]);

  async function markAsRead(alert: AlertOut) {
    if (alert.read_at) return;

    // optimistic update
    setAlerts((prev) =>
      prev.map((a) =>
        a.id === alert.id ? { ...a, read_at: new Date().toISOString() } : a,
      ),
    );

    try {
      await markAlertRead(alert.id);
    } catch {
      // revert
      setAlerts((prev) =>
        prev.map((a) =>
          a.id === alert.id ? { ...a, read_at: null } : a,
        ),
      );
      showToast('읽음 처리에 실패했습니다', 'error');
    }
  }

  function handleTypeFilter(v: string) {
    setTypeFilter(v);
    setOffset(0);
  }

  function handleReadFilter(v: string) {
    setReadFilter(v);
    setOffset(0);
  }

  return (
    <div className="p-4 max-w-lg mx-auto">
      <Toast toasts={toasts} onRemove={removeToast} />

      <h2 className="text-xl font-bold text-gray-800 mb-4">알림</h2>

      {/* Type filter chips */}
      <FilterChips options={ALERT_TYPES} value={typeFilter} onChange={handleTypeFilter} className="mb-3" />

      {/* Read filter */}
      <div className="flex gap-2 mb-4">
        {READ_FILTERS.map((f) => (
          <button
            key={f.value}
            onClick={() => handleReadFilter(f.value)}
            className={`px-3 py-1 text-xs font-medium rounded-lg transition-colors ${
              readFilter === f.value
                ? 'bg-gray-800 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {loading ? (
        <Spinner />
      ) : alerts.length === 0 ? (
        <EmptyState message="알림이 없습니다" />
      ) : (
        <>
          <div className="space-y-2">
            {alerts.map((alert) => (
              <div
                key={alert.id}
                onClick={() => markAsRead(alert)}
                className={`flex items-start gap-3 p-3 bg-white rounded-lg border-l-4 shadow-sm cursor-pointer transition-colors hover:bg-gray-50 ${alertColor(alert.alert_type)}`}
              >
                {/* Unread dot */}
                <div className="flex-shrink-0 mt-1">
                  {!alert.read_at ? (
                    <span className="inline-block w-2 h-2 bg-blue-500 rounded-full" />
                  ) : (
                    <span className="inline-block w-2 h-2" />
                  )}
                </div>
                <span className="text-lg flex-shrink-0">{alertIcon(alert.alert_type)}</span>
                <div className="flex-1 min-w-0">
                  <p className={`text-sm ${!alert.read_at ? 'font-bold text-gray-800' : 'text-gray-600'}`}>
                    {alert.message}
                  </p>
                  <p className="text-xs text-gray-400 mt-1">{timeAgo(alert.sent_at)}</p>
                </div>
              </div>
            ))}
          </div>
          <Pagination total={total} limit={LIMIT} offset={offset} onChange={setOffset} />
        </>
      )}
    </div>
  );
}

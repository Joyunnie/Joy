import { useCallback, useEffect, useRef, useState } from 'react';
import { AlertTriangle, Bell, Calendar, CheckCheck, ShieldAlert } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { fetchAlerts, markAlertRead } from '../api/alertsApi.ts';
import type { AlertOut } from '../types/api.ts';
import Card from '../components/common/Card.tsx';
import PageHeader from '../components/common/PageHeader.tsx';
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

function alertIcon(type: string): LucideIcon {
  switch (type) {
    case 'LOW_STOCK': return AlertTriangle;
    case 'NARCOTICS_LOW': return ShieldAlert;
    case 'VISIT_APPROACHING': return Calendar;
    default: return Bell;
  }
}

function alertVariant(type: string): 'warning' | 'danger' | 'info' | 'default' {
  switch (type) {
    case 'LOW_STOCK': return 'warning';
    case 'NARCOTICS_LOW': return 'danger';
    case 'VISIT_APPROACHING': return 'info';
    default: return 'default';
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

  async function markAllRead() {
    const unread = alerts.filter(a => !a.read_at);
    if (unread.length === 0) return;
    setAlerts(prev => prev.map(a => a.read_at ? a : { ...a, read_at: new Date().toISOString() }));
    try {
      await Promise.all(unread.map(a => markAlertRead(a.id)));
    } catch {
      showToast('일괄 읽음 처리에 실패했습니다', 'error');
      loadAlerts();
    }
  }

  return (
    <div className="p-4 max-w-lg mx-auto">
      <Toast toasts={toasts} onRemove={removeToast} />

      <PageHeader
        title="알림"
        action={
          <button
            onClick={markAllRead}
            className="flex items-center gap-1 text-xs text-gray-500 hover:text-blue-600 transition-colors"
          >
            <CheckCheck size={14} />
            모두 읽음
          </button>
        }
      />

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
              <Card
                key={alert.id}
                onClick={() => markAsRead(alert)}
                variant={alertVariant(alert.alert_type)}
                borderAccent
                className="flex items-start gap-3"
              >
                {/* Unread dot */}
                <div className="flex-shrink-0 mt-1">
                  {!alert.read_at ? (
                    <span className="inline-block w-2 h-2 bg-blue-500 rounded-full" />
                  ) : (
                    <span className="inline-block w-2 h-2" />
                  )}
                </div>
                {(() => { const Icon = alertIcon(alert.alert_type); return <Icon size={18} className="flex-shrink-0 text-gray-500" />; })()}
                <div className="flex-1 min-w-0">
                  <p className={`text-sm ${!alert.read_at ? 'font-medium text-gray-800' : 'text-gray-500'}`}>
                    {alert.message}
                  </p>
                  <p className="text-xs text-gray-400 mt-1">{timeAgo(alert.sent_at)}</p>
                </div>
              </Card>
            ))}
          </div>
          <Pagination total={total} limit={LIMIT} offset={offset} onChange={setOffset} />
        </>
      )}
    </div>
  );
}

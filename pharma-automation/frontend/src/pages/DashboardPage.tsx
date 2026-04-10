import { useCallback, useEffect, useRef, useState } from 'react';
import { AlertTriangle, Calendar, ChevronRight, Package } from 'lucide-react';

const POLL_INTERVAL_MS = 60_000;
import { Link } from 'react-router-dom';
import api from '../api/client.ts';
import { fetchAlerts } from '../api/alertsApi.ts';
import { fetchPredictions } from '../api/predictionsApi.ts';
import { fetchTodos, toggleComplete, type TodoItem } from '../api/todos.ts';
import Spinner from '../components/Spinner.tsx';
import Toast from '../components/Toast.tsx';
import PageHeader from '../components/common/PageHeader.tsx';
import { useToast } from '../hooks/useToast.ts';
import type {
  InventoryStatusResponse,
  NarcoticsListResponse,
  OtcListResponse,
} from '../types/api.ts';

interface DashboardData {
  unreadAlerts: number;
  recentAlerts: Array<{ id: number; message: string; alert_type: string }>;
  otcLowStock: number;
  prescriptionLowStock: number;
  narcoticsLowStock: number;
  predictionsThisWeek: number;
  predictionsToday: number;
}

function todayStr(): string {
  return new Date().toISOString().slice(0, 10);
}

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [todos, setTodos] = useState<TodoItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const { toasts, showToast, removeToast } = useToast();

  useEffect(() => {
    let cancelled = false;

    async function fetchAll() {
      try {
        const [alertsData, otcRes, narcLowRes, prescRes, predData, todosRes] =
          await Promise.all([
            fetchAlerts({ is_read: false, limit: 5 }),
            api.get<OtcListResponse>('/otc-inventory', {
              params: { low_stock_only: true, limit: 1 },
            }),
            api.get<NarcoticsListResponse>('/narcotics-inventory', {
              params: { low_stock_only: true, limit: 1 },
            }),
            api.get<InventoryStatusResponse>('/inventory/status', {
              params: { low_stock_only: true },
            }),
            fetchPredictions(7),
            fetchTodos('today'),
          ]);

        if (cancelled) return;

        const today = todayStr();
        const predictionsToday = predData.predictions.filter(
          (p) => p.predicted_visit_date === today,
        ).length;

        setTodos(todosRes.items);
        setData({
          unreadAlerts: alertsData.total,
          recentAlerts: alertsData.alerts.map((a) => ({
            id: a.id,
            message: a.message,
            alert_type: a.alert_type,
          })),
          otcLowStock: otcRes.data.total,
          prescriptionLowStock: prescRes.data.items.length,
          narcoticsLowStock: narcLowRes.data.total,
          predictionsThisWeek: predData.predictions.length,
          predictionsToday,
        });
      } catch {
        if (!cancelled) setError('데이터를 불러오지 못했습니다');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchAll();
    return () => { cancelled = true; };
  }, []);

  const polling = useRef(false);
  const pollAlerts = useCallback(async () => {
    if (polling.current) return;
    polling.current = true;
    try {
      const alertData = await fetchAlerts({ is_read: false, limit: 5 });
      setData(prev => prev ? {
        ...prev,
        unreadAlerts: alertData.total,
        recentAlerts: alertData.alerts.map(a => ({
          id: a.id, message: a.message, alert_type: a.alert_type,
        })),
      } : null);
    } catch (e) { console.warn('Alert poll failed', e); }
    finally { polling.current = false; }
  }, [fetchAlerts]);

  useEffect(() => {
    const id = setInterval(() => {
      if (!document.hidden) pollAlerts();
    }, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [pollAlerts]);

  if (loading) {
    return (
      <Spinner containerHeight="h-64" />
    );
  }

  if (error) {
    return (
      <div className="p-4 text-center text-red-600">{error}</div>
    );
  }

  if (!data) return null;

  async function handleToggleTodo(id: number) {
    try {
      const updated = await toggleComplete(id);
      setTodos((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
    } catch {
      showToast('상태 변경에 실패했습니다', 'error');
    }
  }

  function formatTime(dateStr: string | null): string {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    return d.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' });
  }

  const totalLowStock =
    data.otcLowStock + data.prescriptionLowStock + data.narcoticsLowStock;

  return (
    <div className="p-4 space-y-4 max-w-lg mx-auto">
      <Toast toasts={toasts} onRemove={removeToast} />
      <PageHeader title="대시보드" />

      {/* 오늘 할 일 */}
      <Link
        to="/todos"
        className="block bg-white rounded-xl shadow-sm hover:shadow-md transition-shadow duration-150 border border-gray-100 overflow-hidden"
      >
        <div className="flex items-center justify-between bg-gray-50 rounded-t-xl px-4 py-2.5 border-b border-gray-100">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-gray-600">오늘 할 일</h3>
            {todos.length > 0 && (
              <span className="rounded-full bg-blue-100 text-blue-700 text-xs px-2 font-medium">
                {todos.length}
              </span>
            )}
          </div>
          <ChevronRight size={16} className="text-gray-400" />
        </div>
        <div className="p-4">
          {todos.length > 0 ? (
            <ul className="space-y-2">
              {todos.map((todo) => (
                <li key={todo.id} className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={todo.is_completed}
                    onChange={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      handleToggleTodo(todo.id);
                    }}
                    onClick={(e) => e.stopPropagation()}
                    className="w-4 h-4 rounded border-gray-300 text-blue-600 flex-shrink-0"
                  />
                  <span className={`text-sm flex-1 truncate ${todo.is_completed ? 'line-through text-gray-400' : 'text-gray-700'}`}>
                    {todo.title}
                  </span>
                  {todo.due_date && (
                    <span className="text-xs text-gray-400 flex-shrink-0">
                      {formatTime(todo.due_date)}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-gray-400">오늘 할 일이 없습니다</p>
          )}
        </div>
      </Link>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {/* Card 1: Alerts */}
        <Link
          to="/alerts"
          className="block bg-white rounded-xl shadow-sm p-4 hover:shadow-md transition-shadow duration-150 border border-gray-100"
        >
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-full bg-orange-50 flex items-center justify-center flex-shrink-0">
              <AlertTriangle size={20} className="text-orange-500" />
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="text-sm font-semibold text-gray-600">새 알림</h3>
              {data.unreadAlerts > 0 && (
                <span className="text-xs text-orange-600 font-medium">{data.unreadAlerts}건</span>
              )}
            </div>
          </div>
          {data.recentAlerts.length > 0 ? (
            <ul className="space-y-1">
              {data.recentAlerts.map((alert) => (
                <li key={alert.id} className="text-xs text-gray-500 truncate">
                  {alert.message}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-gray-400">새 알림 없음</p>
          )}
        </Link>

        {/* Card 2: Low Stock */}
        <Link
          to="/inventory"
          className="block bg-white rounded-xl shadow-sm p-4 hover:shadow-md transition-shadow duration-150 border border-gray-100"
        >
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-full bg-red-50 flex items-center justify-center flex-shrink-0">
              <Package size={20} className="text-red-500" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-gray-600">재고 부족</h3>
              <p className="text-2xl font-bold text-red-600">{totalLowStock}건</p>
            </div>
          </div>
          <div className="text-xs text-gray-500 space-y-0.5">
            <p>OTC {data.otcLowStock}건</p>
            <p>전문 {data.prescriptionLowStock}건</p>
            <p>마약류 {data.narcoticsLowStock}건</p>
          </div>
        </Link>

        {/* Card 3: Predictions */}
        <Link
          to="/predictions"
          className="block bg-white rounded-xl shadow-sm p-4 hover:shadow-md transition-shadow duration-150 border border-gray-100"
        >
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-full bg-blue-50 flex items-center justify-center flex-shrink-0">
              <Calendar size={20} className="text-blue-500" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-gray-600">예상 내원</h3>
              <p className="text-2xl font-bold text-blue-600">{data.predictionsThisWeek}명</p>
            </div>
          </div>
          <p className="text-xs text-gray-500">
            오늘 예상: <span className="font-semibold text-blue-700">{data.predictionsToday}명</span>
          </p>
        </Link>
      </div>
    </div>
  );
}

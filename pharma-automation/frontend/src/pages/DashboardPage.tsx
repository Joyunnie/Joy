// TODO(Phase 3B): GET /dashboard/summary 통합 API 검토
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api from '../api/client.ts';
import type {
  AlertListResponse,
  InventoryStatusResponse,
  NarcoticsListResponse,
  OtcListResponse,
  PredictionListResponse,
} from '../types/api.ts';

interface DashboardData {
  unreadAlerts: number;
  recentAlerts: Array<{ id: number; message: string; alert_type: string }>;
  otcLowStock: number;
  prescriptionLowStock: number;
  narcoticsLowStock: number;
  predictionsThisWeek: number;
  predictionsToday: number;
  narcoticsActive: number;
  narcoticsLow: number;
}

function todayStr(): string {
  return new Date().toISOString().slice(0, 10);
}

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;

    async function fetchAll() {
      try {
        // TODO(Phase 3B): GET /dashboard/summary 통합 API 검토
        const [alertsRes, otcRes, narcLowRes, prescRes, predRes, narcAllRes] =
          await Promise.all([
            api.get<AlertListResponse>('/alerts', {
              params: { unread_only: true, limit: 5 },
            }),
            api.get<OtcListResponse>('/otc-inventory', {
              params: { low_stock_only: true, limit: 1 },
            }),
            api.get<NarcoticsListResponse>('/narcotics-inventory', {
              params: { low_stock_only: true, limit: 1 },
            }),
            api.get<InventoryStatusResponse>('/inventory/status', {
              params: { low_stock_only: true },
            }),
            api.get<PredictionListResponse>('/predictions', {
              params: { days_ahead: 7 },
            }),
            api.get<NarcoticsListResponse>('/narcotics-inventory', {
              params: { limit: 1 },
            }),
          ]);

        if (cancelled) return;

        const today = todayStr();
        const predictionsToday = predRes.data.predictions.filter(
          (p) => p.predicted_visit_date === today,
        ).length;

        setData({
          unreadAlerts: alertsRes.data.total,
          recentAlerts: alertsRes.data.alerts.map((a) => ({
            id: a.id,
            message: a.message,
            alert_type: a.alert_type,
          })),
          otcLowStock: otcRes.data.total,
          prescriptionLowStock: prescRes.data.items.length,
          narcoticsLowStock: narcLowRes.data.total,
          predictionsThisWeek: predRes.data.predictions.length,
          predictionsToday,
          narcoticsActive: narcAllRes.data.total,
          narcoticsLow: narcLowRes.data.total,
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

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <span className="inline-block w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 text-center text-red-600">{error}</div>
    );
  }

  if (!data) return null;

  const totalLowStock =
    data.otcLowStock + data.prescriptionLowStock + data.narcoticsLowStock;

  return (
    <div className="p-4 space-y-4 max-w-lg mx-auto">
      <h2 className="text-xl font-bold text-gray-800">대시보드</h2>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {/* Card 1: Alerts */}
        <Link
          to="/alerts"
          className="block bg-white rounded-lg shadow p-4 hover:shadow-md transition-shadow border border-gray-100"
        >
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-semibold text-gray-600">새 알림</h3>
            {data.unreadAlerts > 0 && (
              <span className="bg-red-500 text-white text-xs font-bold px-2 py-0.5 rounded-full">
                {data.unreadAlerts}
              </span>
            )}
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
          className="block bg-white rounded-lg shadow p-4 hover:shadow-md transition-shadow border border-gray-100"
        >
          <h3 className="text-sm font-semibold text-gray-600 mb-2">재고 부족</h3>
          <p className="text-3xl font-bold text-orange-600">{totalLowStock}건</p>
          <div className="mt-2 text-xs text-gray-500 space-y-0.5">
            <p>OTC {data.otcLowStock}건</p>
            <p>전문 {data.prescriptionLowStock}건</p>
            <p>마약류 {data.narcoticsLowStock}건</p>
          </div>
        </Link>

        {/* Card 3: Predictions */}
        <Link
          to="/predictions"
          className="block bg-white rounded-lg shadow p-4 hover:shadow-md transition-shadow border border-gray-100"
        >
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-semibold text-gray-600">예상 내원</h3>
            <span className="text-xs text-blue-500">더보기 &rarr;</span>
          </div>
          <div className="flex items-baseline gap-2">
            <p className="text-3xl font-bold text-blue-600">
              {data.predictionsThisWeek}명
            </p>
            <span className="text-sm text-gray-400">이번 주</span>
          </div>
          <p className="mt-1 text-sm text-gray-500">
            오늘 예상: <span className="font-semibold text-blue-700">{data.predictionsToday}명</span>
          </p>
        </Link>

        {/* Card 4: Narcotics (링크 없음 — PM+20이 별도 관리) */}
        <div className="bg-white rounded-lg shadow p-4 border border-gray-100">
          <h3 className="text-sm font-semibold text-gray-600 mb-2">마약류 현황</h3>
          <p className="text-3xl font-bold text-purple-600">{data.narcoticsActive}건</p>
          <p className="text-sm text-gray-400">활성 품목</p>
          {data.narcoticsLow > 0 && (
            <p className="mt-1 text-sm text-red-500">
              재고 부족 {data.narcoticsLow}건
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

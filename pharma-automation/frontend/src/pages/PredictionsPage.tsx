import { useCallback, useEffect, useState } from 'react';
import api from '../api/client.ts';
import type { PredictionListResponse, PredictionOut } from '../types/api.ts';
import EmptyState from '../components/EmptyState.tsx';
import Toast from '../components/Toast.tsx';
import { useToast } from '../hooks/useToast.ts';

const DAYS_OPTIONS = [
  { value: 1, label: '오늘' },
  { value: 3, label: '3일' },
  { value: 7, label: '7일' },
  { value: 14, label: '14일' },
  { value: 30, label: '30일' },
] as const;

function maskHash(hash: string): string {
  if (hash.length <= 6) return hash;
  return `${hash.slice(0, 3)}...${hash.slice(-3)}`;
}

function groupByDate(predictions: PredictionOut[]): Map<string, PredictionOut[]> {
  const map = new Map<string, PredictionOut[]>();
  for (const p of predictions) {
    const key = p.predicted_visit_date;
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(p);
  }
  return map;
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00');
  const weekdays = ['일', '월', '화', '수', '목', '금', '토'];
  return `${d.getMonth() + 1}/${d.getDate()} (${weekdays[d.getDay()]})`;
}

export default function PredictionsPage() {
  const [predictions, setPredictions] = useState<PredictionOut[]>([]);
  const [daysAhead, setDaysAhead] = useState(7);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const { toasts, showToast, removeToast } = useToast();

  const fetchPredictions = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get<PredictionListResponse>('/predictions', {
        params: { days_ahead: daysAhead },
      });
      setPredictions(data.predictions);
    } catch {
      showToast('예측 데이터를 불러오지 못했습니다', 'error');
    } finally {
      setLoading(false);
    }
  }, [daysAhead, showToast]);

  useEffect(() => { fetchPredictions(); }, [fetchPredictions]);

  function toggleExpand(id: number) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  const grouped = groupByDate(predictions);

  return (
    <div className="p-4 max-w-lg mx-auto">
      <Toast toasts={toasts} onRemove={removeToast} />

      <h2 className="text-xl font-bold text-gray-800 mb-4">내원 예측</h2>

      {/* Days ahead chips */}
      <div className="flex gap-2 overflow-x-auto pb-2 mb-4 scrollbar-hide">
        {DAYS_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            onClick={() => setDaysAhead(opt.value)}
            className={`px-3 py-1 text-xs font-medium rounded-full whitespace-nowrap transition-colors ${
              daysAhead === opt.value
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-40">
          <span className="inline-block w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : predictions.length === 0 ? (
        <EmptyState message="예측 데이터가 없습니다" />
      ) : (
        <div className="space-y-4">
          {[...grouped.entries()].map(([date, items]) => (
            <div key={date}>
              <h3 className="text-sm font-semibold text-gray-500 mb-2 sticky top-0 bg-gray-50 py-1">
                {formatDate(date)}
                <span className="ml-2 text-xs text-gray-400">{items.length}명</span>
              </h3>
              <div className="space-y-2">
                {items.map((pred) => (
                  <div
                    key={pred.id}
                    className="bg-white rounded-lg shadow-sm border border-gray-100 p-3"
                  >
                    <div
                      className="flex items-center justify-between cursor-pointer"
                      onClick={() => toggleExpand(pred.id)}
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-mono text-gray-700">
                          {maskHash(pred.patient_hash)}
                        </span>
                        {pred.is_overdue && (
                          <span className="text-xs bg-red-100 text-red-600 px-1.5 py-0.5 rounded font-medium">
                            지남
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-gray-400">{pred.prediction_method}</span>
                        <span className="text-gray-400 text-xs">
                          {expanded.has(pred.id) ? '▲' : '▼'}
                        </span>
                      </div>
                    </div>

                    {/* Expandable drug list */}
                    {expanded.has(pred.id) && pred.needed_drugs.length > 0 && (
                      <div className="mt-3 pt-3 border-t border-gray-100 space-y-1">
                        {pred.needed_drugs.map((drug, idx) => (
                          <div key={idx} className="flex justify-between text-xs">
                            <span className="text-gray-600">{drug.drug_name}</span>
                            <span className={
                              drug.in_stock !== null && drug.in_stock < drug.quantity
                                ? 'text-red-500 font-medium'
                                : 'text-gray-500'
                            }>
                              필요 {drug.quantity} / 재고 {drug.in_stock ?? '-'}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

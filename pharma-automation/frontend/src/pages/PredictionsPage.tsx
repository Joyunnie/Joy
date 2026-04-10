import { useCallback, useEffect, useMemo, useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { fetchPredictions } from '../api/predictionsApi.ts';
import type { PredictionOut } from '../types/api.ts';
import Card from '../components/common/Card.tsx';
import EmptyState from '../components/EmptyState.tsx';
import Spinner from '../components/Spinner.tsx';
import FilterChips from '../components/FilterChips.tsx';
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

  const loadPredictions = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchPredictions(daysAhead);
      setPredictions(data.predictions);
    } catch {
      showToast('예측 데이터를 불러오지 못했습니다', 'error');
    } finally {
      setLoading(false);
    }
  }, [daysAhead, showToast]);

  useEffect(() => { loadPredictions(); }, [loadPredictions]);

  const toggleExpand = useCallback((id: number) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const grouped = useMemo(() => groupByDate(predictions), [predictions]);

  return (
    <div className="p-4 max-w-lg mx-auto">
      <Toast toasts={toasts} onRemove={removeToast} />

      <h2 className="text-xl font-bold text-gray-800 mb-4">내원 예측</h2>

      {/* Days ahead chips */}
      <FilterChips options={DAYS_OPTIONS} value={daysAhead} onChange={setDaysAhead} className="mb-4" />

      {loading ? (
        <Spinner />
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
                  <Card key={pred.id}>
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
                        {expanded.has(pred.id)
                          ? <ChevronUp size={14} className="text-gray-400" />
                          : <ChevronDown size={14} className="text-gray-400" />
                        }
                      </div>
                    </div>

                    {/* Expandable drug list */}
                    {expanded.has(pred.id) && pred.needed_drugs.length > 0 && (
                      <div className="mt-3 pt-3 border-t border-gray-100 space-y-1">
                        {pred.needed_drugs.map((drug, idx) => (
                          <div key={idx} className="flex justify-between text-xs">
                            <span className="text-gray-600">{drug.drug_name}</span>
                            <span className="text-gray-500">
                              필요 {drug.quantity}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </Card>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

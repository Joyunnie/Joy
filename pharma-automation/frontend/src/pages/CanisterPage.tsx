import { useCallback, useEffect, useMemo, useState } from 'react';
import { X } from 'lucide-react';
import {
  fetchCanisters,
  upsertCanister,
  type CanisterItem,
} from '../api/canisters.ts';

const TOTAL_SLOTS = 156;

interface EditState {
  canisterNumber: number;
  drugCode: string;
  drugName: string;
}

export default function CanisterPage() {
  const [canisters, setCanisters] = useState<CanisterItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [editing, setEditing] = useState<EditState | null>(null);
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const resp = await fetchCanisters();
      setCanisters(resp.items);
      setLoadError(null);
    } catch {
      setLoadError('캐니스터 목록을 불러오지 못했습니다');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Map canister_number → CanisterItem + filter in one pass
  const filteredSlots = useMemo(() => {
    const map = new Map<number, CanisterItem>();
    for (const c of canisters) map.set(c.canister_number, c);
    const q = search.trim().toLowerCase();
    return Array.from({ length: TOTAL_SLOTS }, (_, i) => {
      const number = i + 1;
      const item = map.get(number);
      return { number, item };
    }).filter(s =>
      !q ||
      s.item?.drug_name.toLowerCase().includes(q) ||
      s.item?.drug_code.toLowerCase().includes(q) ||
      String(s.number).includes(q)
    );
  }, [canisters, search]);

  const filledCount = canisters.length;

  function handleSlotClick(num: number) {
    const item = canisters.find(c => c.canister_number === num);
    setEditing({
      canisterNumber: num,
      drugCode: item?.drug_code ?? '',
      drugName: item?.drug_name ?? '',
    });
    setSaveError(null);
  }

  async function handleSave() {
    if (!editing) return;
    if (!editing.drugCode.trim() || !editing.drugName.trim()) {
      setSaveError('약품코드와 약품명을 모두 입력하세요');
      return;
    }
    setSaving(true);
    setSaveError(null);
    try {
      await upsertCanister(editing.canisterNumber, editing.drugCode.trim(), editing.drugName.trim());
      setEditing(null);
      await load();
    } catch {
      setSaveError('저장에 실패했습니다');
    } finally {
      setSaving(false);
    }
  }

  async function handleClear() {
    if (!editing) return;
    if (!window.confirm(`슬롯 #${editing.canisterNumber} 약품 배정을 삭제하시겠습니까?`)) return;
    setSaving(true);
    setSaveError(null);
    try {
      await upsertCanister(editing.canisterNumber, null, null);
      setEditing(null);
      await load();
    } catch {
      setSaveError('삭제에 실패했습니다');
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <div className="p-4 text-center text-gray-500">로딩 중...</div>;
  }

  return (
    <div className="pb-20">
      {/* Header */}
      <div className="sticky top-0 bg-white border-b px-4 py-3 z-10">
        <div className="flex items-center justify-between mb-2">
          <h1 className="text-lg font-bold">캐니스터 매핑</h1>
          <span className="text-sm text-gray-500">
            {filledCount}/{TOTAL_SLOTS} 슬롯 사용
          </span>
        </div>
        {loadError && (
          <div className="text-red-600 text-xs mb-2">{loadError}</div>
        )}
        <input
          type="text"
          placeholder="약품명, 코드, 슬롯번호 검색..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
        />
      </div>

      {/* Grid */}
      <div className="grid grid-cols-4 gap-1.5 p-2">
        {filteredSlots.map(slot => {
          const filled = !!slot.item;
          const isEditing = editing?.canisterNumber === slot.number;
          return (
            <button
              key={slot.number}
              onClick={() => handleSlotClick(slot.number)}
              className={`
                rounded-lg p-1.5 text-left border transition-colors min-h-[56px]
                ${isEditing
                  ? 'border-blue-500 bg-blue-50 ring-2 ring-blue-300'
                  : filled
                    ? 'border-gray-300 bg-white hover:border-blue-400'
                    : 'border-gray-200 bg-gray-50 hover:border-gray-300'
                }
              `}
            >
              <div className={`text-[10px] font-bold ${filled ? 'text-blue-600' : 'text-gray-400'}`}>
                #{slot.number}
              </div>
              <div className={`text-[11px] leading-tight truncate ${filled ? 'text-gray-800' : 'text-gray-400'}`}>
                {filled ? slot.item!.drug_name : '빈 슬롯'}
              </div>
            </button>
          );
        })}
      </div>

      {/* Edit Panel */}
      {editing && (
        <div className="fixed bottom-14 left-0 right-0 bg-white border-t shadow-lg p-4 z-40">
          <div className="max-w-lg mx-auto">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-bold text-sm">슬롯 #{editing.canisterNumber}</h2>
              <button
                onClick={() => setEditing(null)}
                className="text-gray-400 hover:text-gray-600"
              >
                <X size={20} />
              </button>
            </div>

            {saveError && (
              <div className="text-red-600 text-xs mb-2">{saveError}</div>
            )}

            <div className="space-y-2 mb-3">
              <input
                type="text"
                placeholder="약품코드 (보험코드)"
                value={editing.drugCode}
                onChange={e => setEditing({ ...editing, drugCode: e.target.value })}
                className="w-full px-3 py-2 border rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
              />
              <input
                type="text"
                placeholder="약품명"
                value={editing.drugName}
                onChange={e => setEditing({ ...editing, drugName: e.target.value })}
                className="w-full px-3 py-2 border rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
              />
            </div>

            <div className="flex gap-2">
              <button
                onClick={handleSave}
                disabled={saving}
                className="flex-1 bg-blue-600 text-white py-2 rounded text-sm font-medium disabled:opacity-50"
              >
                {saving ? '저장 중...' : '저장'}
              </button>
              {canisters.some(c => c.canister_number === editing.canisterNumber) && (
                <button
                  onClick={handleClear}
                  disabled={saving}
                  className="px-4 bg-red-50 text-red-600 py-2 rounded text-sm font-medium hover:bg-red-100 disabled:opacity-50"
                >
                  비우기
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

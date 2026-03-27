import { useEffect, useState } from 'react';
import api from '../api/client.ts';
import type { DrugListResponse, DrugOut, ReceiptOcrItemOut } from '../types/api.ts';

interface Props {
  item: ReceiptOcrItemOut;
  recordId: number;
  onUpdated: (updated: ReceiptOcrItemOut) => void;
  onError: (msg: string) => void;
}

export default function ReceiptOcrItemRow({ item, recordId, onUpdated, onError }: Props) {
  const [editing, setEditing] = useState(false);
  const [drugSearch, setDrugSearch] = useState('');
  const [drugResults, setDrugResults] = useState<DrugOut[]>([]);
  const [qty, setQty] = useState(item.confirmed_quantity ?? item.quantity ?? 0);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (drugSearch.length < 1) { setDrugResults([]); return; }
    const timer = setTimeout(async () => {
      try {
        const { data } = await api.get<DrugListResponse>('/drugs', { params: { search: drugSearch, limit: 10 } });
        setDrugResults(data.items);
      } catch { /* ignore */ }
    }, 300);
    return () => clearTimeout(timer);
  }, [drugSearch]);

  async function handleSelectDrug(drug: DrugOut) {
    setSaving(true);
    try {
      const { data } = await api.put<ReceiptOcrItemOut>(
        `/receipt-ocr/${recordId}/items/${item.id}`,
        { drug_id: drug.id, quantity: qty },
      );
      onUpdated(data);
      setEditing(false);
    } catch {
      onError('항목 수정에 실패했습니다');
    } finally {
      setSaving(false);
    }
  }

  async function handleConfirmOnly() {
    setSaving(true);
    try {
      const { data } = await api.put<ReceiptOcrItemOut>(
        `/receipt-ocr/${recordId}/items/${item.id}`,
        { drug_id: item.confirmed_drug_id ?? item.drug_id, quantity: qty },
      );
      onUpdated(data);
    } catch {
      onError('확인에 실패했습니다');
    } finally {
      setSaving(false);
    }
  }

  const scoreColor = (item.match_score ?? 0) >= 0.7
    ? 'text-green-600'
    : (item.match_score ?? 0) >= 0.4
      ? 'text-yellow-600'
      : 'text-red-600';

  return (
    <div className={`bg-white rounded-lg border p-3 ${item.is_confirmed ? 'border-green-200' : 'border-gray-200'}`}>
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="text-sm font-medium text-gray-800">{item.item_name ?? '-'}</p>
          <div className="mt-1 flex items-center gap-2 text-xs text-gray-500">
            <span>수량: {item.confirmed_quantity ?? item.quantity ?? '-'}</span>
            {item.unit_price && <span>단가: {item.unit_price.toLocaleString()}원</span>}
          </div>
          {item.matched_drug_name && (
            <div className="mt-1 flex items-center gap-1.5">
              <span className="text-xs text-gray-600">매칭: {item.matched_drug_name}</span>
              <span className={`text-xs font-medium ${scoreColor}`}>
                ({((item.match_score ?? 0) * 100).toFixed(0)}%)
              </span>
            </div>
          )}
          {!item.matched_drug_name && !item.drug_id && (
            <p className="mt-1 text-xs text-red-500">매칭 실패 - 수동 선택 필요</p>
          )}
        </div>
        <div className="flex items-center gap-1 ml-2">
          {item.is_confirmed && (
            <span className="text-xs bg-green-100 text-green-700 px-1.5 py-0.5 rounded">확인</span>
          )}
          <button
            onClick={() => setEditing(!editing)}
            className="text-xs text-blue-600 hover:text-blue-800 px-1.5 py-0.5"
          >
            수정
          </button>
          {!item.is_confirmed && (item.drug_id || item.confirmed_drug_id) && (
            <button
              onClick={handleConfirmOnly}
              disabled={saving}
              className="text-xs text-green-600 hover:text-green-800 px-1.5 py-0.5 disabled:opacity-50"
            >
              확인
            </button>
          )}
        </div>
      </div>

      {editing && (
        <div className="mt-2 border-t pt-2 space-y-2">
          <div>
            <label className="block text-xs text-gray-500 mb-1">수량</label>
            <input
              type="number"
              min={0}
              value={qty}
              onChange={(e) => setQty(Number(e.target.value))}
              className="w-full px-2 py-1 border border-gray-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">약품 검색</label>
            <input
              type="text"
              value={drugSearch}
              onChange={(e) => setDrugSearch(e.target.value)}
              placeholder="약품명 검색..."
              className="w-full px-2 py-1 border border-gray-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
            {drugResults.length > 0 && (
              <div className="max-h-32 overflow-y-auto border border-gray-200 rounded mt-1">
                {drugResults.map((drug) => (
                  <button
                    key={drug.id}
                    onClick={() => handleSelectDrug(drug)}
                    disabled={saving}
                    className="w-full text-left px-2 py-1.5 text-xs hover:bg-blue-50 border-b border-gray-100 last:border-b-0 disabled:opacity-50"
                  >
                    <span className="font-medium">{drug.name}</span>
                    <span className="text-gray-400 ml-1">{drug.standard_code}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

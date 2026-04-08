import { useEffect, useState } from 'react';
import axios from 'axios';
import api from '../api/client.ts';
import type { DrugListResponse, DrugOut, OtcCreateRequest, OtcItemResponse, OtcUpdateRequest } from '../types/api.ts';
import Modal from './Modal.tsx';

interface Props {
  mode: 'add' | 'edit';
  item?: OtcItemResponse;
  onClose: () => void;
  onSuccess: () => void;
  onError: (msg: string) => void;
}

export default function OtcFormModal({ mode, item, onClose, onSuccess, onError }: Props) {
  const [drugSearch, setDrugSearch] = useState('');
  const [drugResults, setDrugResults] = useState<DrugOut[]>([]);
  const [selectedDrug, setSelectedDrug] = useState<DrugOut | null>(null);
  const [quantity, setQuantity] = useState(item?.current_quantity ?? 0);
  const [displayLoc, setDisplayLoc] = useState(item?.display_location ?? '');
  const [storageLoc, setStorageLoc] = useState(item?.storage_location ?? '');
  const [saving, setSaving] = useState(false);

  // Drug search (add mode only)
  useEffect(() => {
    if (mode !== 'add' || drugSearch.length < 1) { setDrugResults([]); return; }
    const timer = setTimeout(async () => {
      try {
        const { data } = await api.get<DrugListResponse>('/drugs', {
          params: { search: drugSearch, limit: 10 },
        });
        setDrugResults(data.items);
      } catch { /* autocomplete failure is non-critical */ }
    }, 300);
    return () => clearTimeout(timer);
  }, [drugSearch, mode]);

  async function handleSave() {
    setSaving(true);
    try {
      if (mode === 'add') {
        if (!selectedDrug) return;
        const body: OtcCreateRequest = {
          drug_id: selectedDrug.id,
          current_quantity: quantity,
          display_location: displayLoc || null,
          storage_location: storageLoc || null,
        };
        await api.post('/otc-inventory', body);
      } else {
        const body: OtcUpdateRequest = {
          current_quantity: quantity,
          display_location: displayLoc || null,
          storage_location: storageLoc || null,
          version: item!.version,
        };
        await api.put(`/otc-inventory/${item!.id}`, body);
      }
      onSuccess();
    } catch (err: unknown) {
      if (mode === 'edit' && axios.isAxiosError(err) && err.response?.status === 409) {
        onError('다른 사용자가 수정했습니다. 새로고침하세요.');
        return;
      }
      onError(mode === 'add' ? '추가에 실패했습니다' : '수정에 실패했습니다');
    } finally {
      setSaving(false);
    }
  }

  const title = mode === 'add' ? 'OTC 재고 추가' : '재고 수정';

  // Drug selection step (add mode, no drug selected yet)
  if (mode === 'add' && !selectedDrug) {
    return (
      <Modal isOpen onClose={onClose} title={title}>
        <div>
          <input
            type="text"
            value={drugSearch}
            onChange={(e) => setDrugSearch(e.target.value)}
            placeholder="약품명 검색..."
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm mb-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
            autoFocus
          />
          {drugResults.length > 0 && (
            <div className="max-h-48 overflow-y-auto border border-gray-200 rounded-lg">
              {drugResults.map((drug) => (
                <button
                  key={drug.id}
                  onClick={() => setSelectedDrug(drug)}
                  className="w-full text-left px-3 py-2 text-sm hover:bg-blue-50 border-b border-gray-100 last:border-b-0"
                >
                  <p className="font-medium text-gray-800">{drug.name}</p>
                  <p className="text-xs text-gray-400">{drug.standard_code} · {drug.category}</p>
                </button>
              ))}
            </div>
          )}
        </div>
      </Modal>
    );
  }

  // Form (shared by add + edit)
  return (
    <Modal isOpen onClose={onClose} title={title}>
      <div className="space-y-3">
        {mode === 'add' && selectedDrug ? (
          <div className="bg-blue-50 rounded-lg p-2 text-sm">
            <span className="font-medium">{selectedDrug.name}</span>
            <button onClick={() => setSelectedDrug(null)} className="ml-2 text-blue-600 text-xs">변경</button>
          </div>
        ) : (
          <div className="bg-gray-50 rounded-lg p-2 text-sm font-medium text-gray-700">
            {item?.drug_name ?? `Drug #${item?.drug_id}`}
          </div>
        )}
        <div>
          <label className="block text-xs text-gray-600 mb-1">수량</label>
          <input
            type="number"
            min={0}
            value={quantity}
            onChange={(e) => setQuantity(Number(e.target.value))}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-600 mb-1">매장 위치</label>
          <input
            type="text"
            value={displayLoc}
            onChange={(e) => setDisplayLoc(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-600 mb-1">창고 위치</label>
          <input
            type="text"
            value={storageLoc}
            onChange={(e) => setStorageLoc(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <button
          onClick={handleSave}
          disabled={saving}
          className="w-full py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg disabled:opacity-50 transition-colors"
        >
          {saving ? '저장 중...' : '저장'}
        </button>
      </div>
    </Modal>
  );
}

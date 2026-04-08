import { useEffect, useState } from 'react';
import api from '../api/client.ts';
import type { DrugListResponse, DrugOut, OtcCreateRequest } from '../types/api.ts';
import Modal from './Modal.tsx';

interface Props {
  onClose: () => void;
  onSuccess: () => void;
  onError: (msg: string) => void;
}

export default function OtcAddModal({ onClose, onSuccess, onError }: Props) {
  const [drugSearch, setDrugSearch] = useState('');
  const [drugResults, setDrugResults] = useState<DrugOut[]>([]);
  const [selectedDrug, setSelectedDrug] = useState<DrugOut | null>(null);
  const [quantity, setQuantity] = useState(0);
  const [displayLoc, setDisplayLoc] = useState('');
  const [storageLoc, setStorageLoc] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (drugSearch.length < 1) { setDrugResults([]); return; }
    const timer = setTimeout(async () => {
      try {
        const { data } = await api.get<DrugListResponse>('/drugs', {
          params: { search: drugSearch, limit: 10 },
        });
        setDrugResults(data.items);
      } catch { /* autocomplete failure is non-critical */ }
    }, 300);
    return () => clearTimeout(timer);
  }, [drugSearch]);

  async function handleSave() {
    if (!selectedDrug) return;
    setSaving(true);
    try {
      const body: OtcCreateRequest = {
        drug_id: selectedDrug.id,
        current_quantity: quantity,
        display_location: displayLoc || null,
        storage_location: storageLoc || null,
      };
      await api.post('/otc-inventory', body);
      onSuccess();
    } catch {
      onError('추가에 실패했습니다');
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal isOpen onClose={onClose} title="OTC 재고 추가">
      {!selectedDrug ? (
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
      ) : (
        <div className="space-y-3">
          <div className="bg-blue-50 rounded-lg p-2 text-sm">
            <span className="font-medium">{selectedDrug.name}</span>
            <button onClick={() => setSelectedDrug(null)} className="ml-2 text-blue-600 text-xs">변경</button>
          </div>
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
      )}
    </Modal>
  );
}

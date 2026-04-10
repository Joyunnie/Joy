import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, X } from 'lucide-react';
import axios from 'axios';
import api from '../api/client.ts';
import type {
  DrugListResponse,
  DrugOut,
  ThresholdCreateRequest,
  ThresholdItemResponse,
  ThresholdListResponse,
  ThresholdUpdateRequest,
} from '../types/api.ts';
import SearchInput from '../components/SearchInput.tsx';
import Pagination from '../components/Pagination.tsx';
import EmptyState from '../components/EmptyState.tsx';
import Spinner from '../components/Spinner.tsx';
import Modal from '../components/Modal.tsx';
import ConfirmDialog from '../components/ConfirmDialog.tsx';
import Toast from '../components/Toast.tsx';
import { useToast } from '../hooks/useToast.ts';

const LIMIT = 20;

const CATEGORY_OPTIONS = [
  { value: '', label: '전체' },
  { value: 'OTC', label: 'OTC' },
  { value: 'PRESCRIPTION', label: '전문약' },
  { value: 'NARCOTIC', label: '마약류' },
];

const CATEGORY_COLORS: Record<string, string> = {
  OTC: 'bg-green-100 text-green-700',
  PRESCRIPTION: 'bg-blue-100 text-blue-700',
  NARCOTIC: 'bg-red-100 text-red-700',
};

export default function ThresholdsPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<ThresholdItemResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('');
  const [loading, setLoading] = useState(true);
  const { toasts, showToast, removeToast } = useToast();

  const [addOpen, setAddOpen] = useState(false);
  const [editItem, setEditItem] = useState<ThresholdItemResponse | null>(null);
  const [deleteItem, setDeleteItem] = useState<ThresholdItemResponse | null>(null);

  const fetchItems = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, unknown> = { limit: LIMIT, offset };
      if (search) params.search = search;
      if (category) params.category = category;

      const { data } = await api.get<ThresholdListResponse>('/thresholds', { params });
      setItems(data.items);
      setTotal(data.total);
    } catch {
      showToast('임계값 목록을 불러오지 못했습니다', 'error');
    } finally {
      setLoading(false);
    }
  }, [offset, search, category, showToast]);

  useEffect(() => { fetchItems(); }, [fetchItems]);

  function handleSearch(v: string) {
    setSearch(v);
    setOffset(0);
  }

  async function handleToggleActive(item: ThresholdItemResponse) {
    try {
      await api.put(`/thresholds/${item.id}`, {
        min_quantity: item.min_quantity,
        is_active: !item.is_active,
      } satisfies ThresholdUpdateRequest);
      showToast(item.is_active ? '비활성화되었습니다' : '활성화되었습니다');
      fetchItems();
    } catch {
      showToast('변경에 실패했습니다', 'error');
    }
  }

  async function handleDelete() {
    if (!deleteItem) return;
    try {
      await api.delete(`/thresholds/${deleteItem.id}`);
      showToast('삭제되었습니다');
      setDeleteItem(null);
      fetchItems();
    } catch {
      showToast('삭제에 실패했습니다', 'error');
    }
  }

  return (
    <div className="p-4 max-w-lg mx-auto">
      <Toast toasts={toasts} onRemove={removeToast} />

      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <button
            onClick={() => navigate('/inventory')}
            className="text-gray-500 hover:text-gray-700"
          >
            <ArrowLeft size={20} />
          </button>
          <h2 className="text-xl font-bold text-gray-800">최소수량 설정</h2>
        </div>
        <button
          onClick={() => setAddOpen(true)}
          className="px-3 py-1.5 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors"
        >
          추가
        </button>
      </div>

      <div className="flex items-center gap-3 mb-4">
        <SearchInput value={search} onChange={handleSearch} placeholder="약품명 검색..." />
        <select
          value={category}
          onChange={(e) => { setCategory(e.target.value); setOffset(0); }}
          className="px-2 py-1.5 text-xs border border-gray-300 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          {CATEGORY_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      </div>

      {loading ? (
        <Spinner />
      ) : items.length === 0 ? (
        <EmptyState message="설정된 임계값이 없습니다" />
      ) : (
        <>
          <div className="space-y-2">
            {items.map((item) => (
              <div
                key={item.id}
                className="bg-white rounded-lg shadow-sm p-3 border border-gray-100"
              >
                <div className="flex items-start justify-between">
                  <div
                    className="flex-1 cursor-pointer"
                    onClick={() => setEditItem(item)}
                  >
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-medium text-gray-800">
                        {item.drug_name ?? `Drug #${item.drug_id}`}
                      </p>
                      {item.drug_category && (
                        <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${CATEGORY_COLORS[item.drug_category] ?? 'bg-gray-100 text-gray-600'}`}>
                          {item.drug_category}
                        </span>
                      )}
                    </div>
                    <div className="mt-1 text-xs text-gray-500 flex items-center gap-3">
                      <span>최소수량: {item.min_quantity}</span>
                      <button
                        onClick={(e) => { e.stopPropagation(); handleToggleActive(item); }}
                        className={`px-1.5 py-0.5 rounded font-medium ${
                          item.is_active
                            ? 'bg-green-100 text-green-700'
                            : 'bg-gray-100 text-gray-500'
                        }`}
                      >
                        {item.is_active ? '활성' : '비활성'}
                      </button>
                    </div>
                  </div>
                  <button
                    onClick={() => setDeleteItem(item)}
                    className="text-gray-400 hover:text-red-500 ml-2"
                  >
                    <X size={18} />
                  </button>
                </div>
              </div>
            ))}
          </div>
          <Pagination total={total} limit={LIMIT} offset={offset} onChange={setOffset} />
        </>
      )}

      {addOpen && (
        <ThresholdAddModal
          onClose={() => setAddOpen(false)}
          onSuccess={() => { setAddOpen(false); showToast('추가되었습니다'); fetchItems(); }}
          onError={(msg) => showToast(msg, 'error')}
        />
      )}

      {editItem && (
        <ThresholdEditModal
          item={editItem}
          onClose={() => setEditItem(null)}
          onSuccess={() => { setEditItem(null); showToast('수정되었습니다'); fetchItems(); }}
          onError={(msg) => showToast(msg, 'error')}
        />
      )}

      <ConfirmDialog
        isOpen={!!deleteItem}
        onConfirm={handleDelete}
        onCancel={() => setDeleteItem(null)}
        title="임계값 삭제"
        message={`"${deleteItem?.drug_name ?? ''}" 임계값을 정말 삭제하시겠습니까?`}
        confirmLabel="삭제"
        confirmColor="red"
      />
    </div>
  );
}

// --- Threshold Add Modal ---

function ThresholdAddModal({
  onClose,
  onSuccess,
  onError,
}: {
  onClose: () => void;
  onSuccess: () => void;
  onError: (msg: string) => void;
}) {
  const [drugSearch, setDrugSearch] = useState('');
  const [drugResults, setDrugResults] = useState<DrugOut[]>([]);
  const [selectedDrug, setSelectedDrug] = useState<DrugOut | null>(null);
  const [minQuantity, setMinQuantity] = useState(1);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (drugSearch.length < 1) { setDrugResults([]); return; }
    const timer = setTimeout(async () => {
      try {
        const { data } = await api.get<DrugListResponse>('/drugs', {
          params: { search: drugSearch, limit: 10 },
        });
        setDrugResults(data.items);
      } catch { /* ignore */ }
    }, 300);
    return () => clearTimeout(timer);
  }, [drugSearch]);

  async function handleSave() {
    if (!selectedDrug) return;
    setSaving(true);
    try {
      const body: ThresholdCreateRequest = {
        drug_id: selectedDrug.id,
        min_quantity: minQuantity,
      };
      await api.post('/thresholds', body);
      onSuccess();
    } catch (err: unknown) {
      if (axios.isAxiosError(err) && err.response?.status === 409) {
        onError('이 약품의 최소수량이 이미 설정되어 있습니다');
        return;
      }
      onError('추가에 실패했습니다');
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal isOpen onClose={onClose} title="최소수량 추가">
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
            <span className="text-xs text-gray-500 ml-2">{selectedDrug.category}</span>
            <button onClick={() => setSelectedDrug(null)} className="ml-2 text-blue-600 text-xs">변경</button>
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-1">최소수량</label>
            <input
              type="number"
              min={1}
              value={minQuantity}
              onChange={(e) => setMinQuantity(Number(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <button
            onClick={handleSave}
            disabled={saving || minQuantity < 1}
            className="w-full py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg disabled:opacity-50 transition-colors"
          >
            {saving ? '저장 중...' : '저장'}
          </button>
        </div>
      )}
    </Modal>
  );
}

// --- Threshold Edit Modal ---

function ThresholdEditModal({
  item,
  onClose,
  onSuccess,
  onError,
}: {
  item: ThresholdItemResponse;
  onClose: () => void;
  onSuccess: () => void;
  onError: (msg: string) => void;
}) {
  const [minQuantity, setMinQuantity] = useState(item.min_quantity);
  const [isActive, setIsActive] = useState(item.is_active);
  const [saving, setSaving] = useState(false);

  async function handleSave() {
    setSaving(true);
    try {
      const body: ThresholdUpdateRequest = {
        min_quantity: minQuantity,
        is_active: isActive,
      };
      await api.put(`/thresholds/${item.id}`, body);
      onSuccess();
    } catch {
      onError('수정에 실패했습니다');
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal isOpen onClose={onClose} title="최소수량 수정">
      <div className="space-y-3">
        <div className="bg-gray-50 rounded-lg p-2 text-sm font-medium text-gray-700">
          {item.drug_name ?? `Drug #${item.drug_id}`}
          {item.drug_category && (
            <span className={`ml-2 text-xs px-1.5 py-0.5 rounded ${CATEGORY_COLORS[item.drug_category] ?? 'bg-gray-100 text-gray-600'}`}>
              {item.drug_category}
            </span>
          )}
        </div>
        <div>
          <label className="block text-xs text-gray-600 mb-1">최소수량</label>
          <input
            type="number"
            min={1}
            value={minQuantity}
            onChange={(e) => setMinQuantity(Number(e.target.value))}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
          <input
            type="checkbox"
            checked={isActive}
            onChange={(e) => setIsActive(e.target.checked)}
            className="rounded border-gray-300"
          />
          활성화
        </label>
        <button
          onClick={handleSave}
          disabled={saving || minQuantity < 1}
          className="w-full py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg disabled:opacity-50 transition-colors"
        >
          {saving ? '저장 중...' : '저장'}
        </button>
      </div>
    </Modal>
  );
}

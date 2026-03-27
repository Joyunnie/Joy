import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client.ts';
import type {
  DrugListResponse,
  DrugOut,
  OtcCreateRequest,
  OtcItemResponse,
  OtcListResponse,
  OtcUpdateRequest,
} from '../types/api.ts';
import SearchInput from '../components/SearchInput.tsx';
import Pagination from '../components/Pagination.tsx';
import EmptyState from '../components/EmptyState.tsx';
import Modal from '../components/Modal.tsx';
import ConfirmDialog from '../components/ConfirmDialog.tsx';
import Toast from '../components/Toast.tsx';
import { useToast } from '../hooks/useToast.ts';

const LIMIT = 20;

export default function InventoryPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<OtcItemResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [search, setSearch] = useState('');
  const [lowStockOnly, setLowStockOnly] = useState(false);
  const [loading, setLoading] = useState(true);
  const { toasts, showToast, removeToast } = useToast();

  // modal states
  const [addOpen, setAddOpen] = useState(false);
  const [editItem, setEditItem] = useState<OtcItemResponse | null>(null);
  const [deleteItem, setDeleteItem] = useState<OtcItemResponse | null>(null);

  const fetchItems = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, unknown> = { limit: LIMIT, offset };
      if (search) params.search = search;
      if (lowStockOnly) params.low_stock_only = true;

      const { data } = await api.get<OtcListResponse>('/otc-inventory', { params });
      setItems(data.items);
      setTotal(data.total);
    } catch {
      showToast('재고 목록을 불러오지 못했습니다', 'error');
    } finally {
      setLoading(false);
    }
  }, [offset, search, lowStockOnly, showToast]);

  useEffect(() => { fetchItems(); }, [fetchItems]);

  function handleSearch(v: string) {
    setSearch(v);
    setOffset(0);
  }

  async function handleDelete() {
    if (!deleteItem) return;
    try {
      await api.delete(`/otc-inventory/${deleteItem.id}`);
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
        <h2 className="text-xl font-bold text-gray-800">OTC 재고</h2>
        <div className="flex items-center gap-2">
          <button
            onClick={() => navigate('/prescription-ocr')}
            className="px-3 py-1.5 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
          >
            처방전
          </button>
          <button
            onClick={() => navigate('/receipt-ocr')}
            className="px-3 py-1.5 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
          >
            입고 OCR
          </button>
          <button
            onClick={() => navigate('/shelf')}
            className="px-3 py-1.5 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
          >
            약장 보기
          </button>
          <button
            onClick={() => navigate('/thresholds')}
            className="px-3 py-1.5 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
          >
            최소수량
          </button>
          <button
            onClick={() => setAddOpen(true)}
            className="px-3 py-1.5 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors"
          >
            추가
          </button>
        </div>
      </div>

      <div className="flex items-center gap-3 mb-4">
        <SearchInput value={search} onChange={handleSearch} placeholder="약품명 검색..." />
        <label className="flex items-center gap-1.5 text-xs text-gray-600 whitespace-nowrap cursor-pointer">
          <input
            type="checkbox"
            checked={lowStockOnly}
            onChange={(e) => { setLowStockOnly(e.target.checked); setOffset(0); }}
            className="rounded border-gray-300"
          />
          부족만
        </label>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-40">
          <span className="inline-block w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : items.length === 0 ? (
        <EmptyState message="재고 항목이 없습니다" />
      ) : (
        <>
          <div className="space-y-2">
            {items.map((item) => (
              <div
                key={item.id}
                className={`bg-white rounded-lg shadow-sm p-3 border ${
                  item.is_low_stock ? 'border-red-300' : 'border-gray-100'
                }`}
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
                      {item.is_low_stock && (
                        <span className="text-xs bg-red-100 text-red-600 px-1.5 py-0.5 rounded font-medium">
                          부족
                        </span>
                      )}
                    </div>
                    <div className="mt-1 text-xs text-gray-500 space-y-0.5">
                      <p>수량: {item.current_quantity}{item.min_quantity != null && ` (최소 ${item.min_quantity})`}</p>
                      {item.display_location && <p>매장: {item.display_location}</p>}
                      {item.storage_location && <p>창고: {item.storage_location}</p>}
                    </div>
                  </div>
                  <button
                    onClick={() => setDeleteItem(item)}
                    className="text-gray-400 hover:text-red-500 text-lg leading-none ml-2"
                  >
                    &times;
                  </button>
                </div>
              </div>
            ))}
          </div>
          <Pagination total={total} limit={LIMIT} offset={offset} onChange={setOffset} />
        </>
      )}

      {/* Add Modal */}
      {addOpen && (
        <OtcAddModal
          onClose={() => setAddOpen(false)}
          onSuccess={() => { setAddOpen(false); showToast('추가되었습니다'); fetchItems(); }}
          onError={(msg) => showToast(msg, 'error')}
        />
      )}

      {/* Edit Modal */}
      {editItem && (
        <OtcEditModal
          item={editItem}
          onClose={() => setEditItem(null)}
          onSuccess={() => { setEditItem(null); showToast('수정되었습니다'); fetchItems(); }}
          onError={(msg) => showToast(msg, 'error')}
        />
      )}

      {/* Delete Confirm */}
      <ConfirmDialog
        isOpen={!!deleteItem}
        onConfirm={handleDelete}
        onCancel={() => setDeleteItem(null)}
        title="항목 삭제"
        message={`"${deleteItem?.drug_name ?? ''}" 항목을 정말 삭제하시겠습니까?`}
        confirmLabel="삭제"
        confirmColor="red"
      />
    </div>
  );
}

// --- OTC Add Modal ---

function OtcAddModal({
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
      } catch { /* ignore */ }
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

// --- OTC Edit Modal ---

function OtcEditModal({
  item,
  onClose,
  onSuccess,
  onError,
}: {
  item: OtcItemResponse;
  onClose: () => void;
  onSuccess: () => void;
  onError: (msg: string) => void;
}) {
  const [quantity, setQuantity] = useState(item.current_quantity);
  const [displayLoc, setDisplayLoc] = useState(item.display_location ?? '');
  const [storageLoc, setStorageLoc] = useState(item.storage_location ?? '');
  const [saving, setSaving] = useState(false);

  async function handleSave() {
    setSaving(true);
    try {
      const body: OtcUpdateRequest = {
        current_quantity: quantity,
        display_location: displayLoc || null,
        storage_location: storageLoc || null,
        version: item.version,
      };
      await api.put(`/otc-inventory/${item.id}`, body);
      onSuccess();
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const resp = (err as { response?: { status?: number } }).response;
        if (resp?.status === 409) {
          onError('다른 사용자가 수정했습니다. 새로고침하세요.');
          return;
        }
      }
      onError('수정에 실패했습니다');
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal isOpen onClose={onClose} title="재고 수정">
      <div className="space-y-3">
        <div className="bg-gray-50 rounded-lg p-2 text-sm font-medium text-gray-700">
          {item.drug_name ?? `Drug #${item.drug_id}`}
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
    </Modal>
  );
}

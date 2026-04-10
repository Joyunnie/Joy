import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { X } from 'lucide-react';
import api from '../api/client.ts';
import Card from '../components/common/Card.tsx';
import type {
  OtcItemResponse,
  OtcListResponse,
} from '../types/api.ts';
import SearchInput from '../components/SearchInput.tsx';
import Pagination from '../components/Pagination.tsx';
import EmptyState from '../components/EmptyState.tsx';
import Spinner from '../components/Spinner.tsx';
import ConfirmDialog from '../components/ConfirmDialog.tsx';
import Toast from '../components/Toast.tsx';
import OtcFormModal from '../components/OtcFormModal.tsx';
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

      <h2 className="text-xl font-bold text-gray-800 mb-3">OTC 재고</h2>
      <div className="flex flex-row items-center gap-2 mb-4 overflow-x-auto whitespace-nowrap">
        <button
          onClick={() => navigate('/receipt-ocr')}
          className="h-9 px-3 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors min-w-fit"
        >
          입고OCR
        </button>
        <button
          onClick={() => navigate('/shelf')}
          className="h-9 px-3 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors min-w-fit"
        >
          약장보기
        </button>
        <button
          onClick={() => navigate('/thresholds')}
          className="h-9 px-3 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors min-w-fit"
        >
          최소수량
        </button>
        <button
          onClick={() => setAddOpen(true)}
          className="h-9 px-3 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors min-w-fit"
        >
          추가
        </button>
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
        <Spinner />
      ) : items.length === 0 ? (
        <EmptyState message="재고 항목이 없습니다" />
      ) : (
        <>
          <div className="space-y-2">
            {items.map((item) => (
              <Card
                key={item.id}
                variant={item.is_low_stock ? 'danger' : 'default'}
                borderAccent={item.is_low_stock}
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
                    className="text-gray-400 hover:text-red-500 ml-2"
                  >
                    <X size={18} />
                  </button>
                </div>
              </Card>
            ))}
          </div>
          <Pagination total={total} limit={LIMIT} offset={offset} onChange={setOffset} />
        </>
      )}

      {addOpen && (
        <OtcFormModal
          mode="add"
          onClose={() => setAddOpen(false)}
          onSuccess={() => { setAddOpen(false); showToast('추가되었습니다'); fetchItems(); }}
          onError={(msg) => showToast(msg, 'error')}
        />
      )}

      {editItem && (
        <OtcFormModal
          mode="edit"
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


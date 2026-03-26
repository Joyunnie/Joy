import { useCallback, useEffect, useState } from 'react';
import api from '../api/client.ts';
import type { OtcItemResponse, OtcListResponse } from '../types/api.ts';
import Modal from './Modal.tsx';

interface DrugPickerProps {
  layoutId: number;
  onSelect: (item: OtcItemResponse) => void;
  onClose: () => void;
}

export default function DrugPicker({ layoutId, onSelect, onClose }: DrugPickerProps) {
  const [items, setItems] = useState<OtcItemResponse[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);

  const fetchItems = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, unknown> = {
        unplaced_for_layout: layoutId,
        limit: 50,
      };
      if (search) params.search = search;
      const { data } = await api.get<OtcListResponse>('/otc-inventory', { params });
      setItems(data.items);
    } catch { /* ignore */ } finally {
      setLoading(false);
    }
  }, [layoutId, search]);

  useEffect(() => {
    const timer = setTimeout(fetchItems, 300);
    return () => clearTimeout(timer);
  }, [fetchItems]);

  return (
    <Modal isOpen onClose={onClose} title="약품 선택">
      <div>
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="약품명 검색..."
          className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm mb-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
          autoFocus
        />
        {loading ? (
          <div className="flex items-center justify-center h-20">
            <span className="inline-block w-6 h-6 border-3 border-blue-600 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : items.length === 0 ? (
          <p className="text-center text-sm text-gray-400 py-4">미배치 약품이 없습니다</p>
        ) : (
          <div className="max-h-60 overflow-y-auto border border-gray-200 rounded-lg">
            {items.map((item) => (
              <button
                key={item.id}
                onClick={() => onSelect(item)}
                className="w-full text-left px-3 py-2 text-sm hover:bg-blue-50 border-b border-gray-100 last:border-b-0"
              >
                <p className="font-medium text-gray-800">{item.drug_name ?? `Drug #${item.drug_id}`}</p>
                <p className="text-xs text-gray-400">수량: {item.current_quantity}</p>
              </button>
            ))}
          </div>
        )}
      </div>
    </Modal>
  );
}

import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client.ts';
import type {
  OtcItemResponse,
  OtcListResponse,
  ShelfLayoutListResponse,
  ShelfLayoutResponse,
} from '../types/api.ts';
import ShelfGrid from '../components/ShelfGrid.tsx';
import ShelfLayoutEditor from '../components/ShelfLayoutEditor.tsx';
import DrugPicker from '../components/DrugPicker.tsx';
import Modal from '../components/Modal.tsx';
import Toast from '../components/Toast.tsx';
import { useToast } from '../hooks/useToast.ts';

type LocationType = 'DISPLAY' | 'STORAGE';

export default function ShelfViewPage() {
  const navigate = useNavigate();
  const { toasts, showToast, removeToast } = useToast();

  const [locationType, setLocationType] = useState<LocationType>('DISPLAY');
  const [layouts, setLayouts] = useState<ShelfLayoutResponse[]>([]);
  const [selectedLayout, setSelectedLayout] = useState<ShelfLayoutResponse | null>(null);
  const [items, setItems] = useState<OtcItemResponse[]>([]);
  const [loading, setLoading] = useState(true);

  // modal states
  const [editorOpen, setEditorOpen] = useState(false);
  const [editLayout, setEditLayout] = useState<ShelfLayoutResponse | undefined>(undefined);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [pickerTarget, setPickerTarget] = useState<{ row: number; col: number } | null>(null);
  const [cellDetail, setCellDetail] = useState<{ item: OtcItemResponse; row: number; col: number } | null>(null);

  // Fetch layouts
  const fetchLayouts = useCallback(async () => {
    try {
      const { data } = await api.get<ShelfLayoutListResponse>('/shelf-layouts', {
        params: { location_type: locationType },
      });
      setLayouts(data.items);
      // Auto-select first layout if current selection is gone
      if (data.items.length > 0) {
        setSelectedLayout((prev) => {
          if (prev && data.items.some((l) => l.id === prev.id)) {
            return data.items.find((l) => l.id === prev.id)!;
          }
          return data.items[0];
        });
      } else {
        setSelectedLayout(null);
      }
    } catch {
      showToast('레이아웃 목록을 불러오지 못했습니다', 'error');
    }
  }, [locationType, showToast]);

  // Fetch items for selected layout
  const fetchItems = useCallback(async () => {
    if (!selectedLayout) {
      setItems([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const { data } = await api.get<OtcListResponse>('/otc-inventory', {
        params: { layout_id: selectedLayout.id, limit: 200 },
      });
      setItems(data.items);
    } catch {
      showToast('약품 목록을 불러오지 못했습니다', 'error');
    } finally {
      setLoading(false);
    }
  }, [selectedLayout, showToast]);

  useEffect(() => { fetchLayouts(); }, [fetchLayouts]);
  useEffect(() => { fetchItems(); }, [fetchItems]);

  function handleCellClick(row: number, col: number, item?: OtcItemResponse) {
    if (item) {
      setCellDetail({ item, row, col });
    } else {
      setPickerTarget({ row, col });
      setPickerOpen(true);
    }
  }

  async function handlePlaceDrug(item: OtcItemResponse) {
    if (!selectedLayout || !pickerTarget) return;
    try {
      await api.post('/otc-inventory/batch-location', {
        layout_id: selectedLayout.id,
        assignments: [{ item_id: item.id, row: pickerTarget.row, col: pickerTarget.col }],
      });
      setPickerOpen(false);
      setPickerTarget(null);
      showToast('약품을 배치했습니다');
      fetchItems();
    } catch {
      showToast('배치에 실패했습니다', 'error');
    }
  }

  async function handleRemoveDrug() {
    if (!selectedLayout || !cellDetail) return;
    try {
      await api.post('/otc-inventory/batch-location-remove', {
        layout_id: selectedLayout.id,
        item_ids: [cellDetail.item.id],
      });
      setCellDetail(null);
      showToast('약품 위치를 제거했습니다');
      fetchItems();
    } catch {
      showToast('제거에 실패했습니다', 'error');
    }
  }

  function handleEditorSave() {
    setEditorOpen(false);
    setEditLayout(undefined);
    showToast('저장되었습니다');
    fetchLayouts();
  }

  return (
    <div className="p-4 max-w-lg mx-auto">
      <Toast toasts={toasts} onRemove={removeToast} />

      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <button
            onClick={() => navigate('/inventory')}
            className="text-gray-500 hover:text-gray-700 text-sm"
          >
            &larr;
          </button>
          <h2 className="text-xl font-bold text-gray-800">약장 관리</h2>
        </div>
      </div>

      {/* Location type tabs */}
      <div className="flex gap-2 mb-4">
        {(['DISPLAY', 'STORAGE'] as const).map((type) => (
          <button
            key={type}
            onClick={() => { setLocationType(type); setSelectedLayout(null); }}
            className={`px-4 py-1.5 text-sm font-medium rounded-lg transition-colors ${
              locationType === type
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {type === 'DISPLAY' ? '매장' : '창고'}
          </button>
        ))}
      </div>

      {/* Layout selector */}
      <div className="flex items-center gap-2 mb-4 overflow-x-auto pb-1">
        {layouts.map((l) => (
          <button
            key={l.id}
            onClick={() => setSelectedLayout(l)}
            className={`flex-shrink-0 px-3 py-1 text-xs font-medium rounded-full transition-colors ${
              selectedLayout?.id === l.id
                ? 'bg-blue-100 text-blue-700 border border-blue-300'
                : 'bg-gray-100 text-gray-600 border border-gray-200 hover:bg-gray-200'
            }`}
          >
            {l.name}
            {selectedLayout?.id === l.id && (
              <span
                onClick={(e) => { e.stopPropagation(); setEditLayout(l); setEditorOpen(true); }}
                className="ml-1.5 text-blue-500 hover:text-blue-700 cursor-pointer"
              >
                &#9998;
              </span>
            )}
          </button>
        ))}
        <button
          onClick={() => { setEditLayout(undefined); setEditorOpen(true); }}
          className="flex-shrink-0 w-7 h-7 flex items-center justify-center text-sm text-gray-500 bg-gray-100 hover:bg-gray-200 rounded-full border border-gray-200 transition-colors"
        >
          +
        </button>
      </div>

      {/* Grid area */}
      {!selectedLayout ? (
        <div className="text-center text-sm text-gray-400 py-10">
          {layouts.length === 0 ? '레이아웃을 추가해 주세요' : '레이아웃을 선택해 주세요'}
        </div>
      ) : loading ? (
        <div className="flex items-center justify-center h-40">
          <span className="inline-block w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : (
        <ShelfGrid
          layout={selectedLayout}
          items={items}
          onCellClick={handleCellClick}
        />
      )}

      {/* Layout Editor Modal */}
      {editorOpen && (
        <ShelfLayoutEditor
          layout={editLayout}
          locationType={locationType}
          onClose={() => { setEditorOpen(false); setEditLayout(undefined); }}
          onSave={handleEditorSave}
          onError={(msg) => showToast(msg, 'error')}
        />
      )}

      {/* Drug Picker Modal */}
      {pickerOpen && selectedLayout && (
        <DrugPicker
          layoutId={selectedLayout.id}
          onSelect={handlePlaceDrug}
          onClose={() => { setPickerOpen(false); setPickerTarget(null); }}
        />
      )}

      {/* Cell Detail Modal */}
      {cellDetail && (
        <Modal isOpen onClose={() => setCellDetail(null)} title="배치 정보">
          <div className="space-y-3">
            <div className="bg-gray-50 rounded-lg p-3">
              <p className="text-sm font-medium text-gray-800">
                {cellDetail.item.drug_name ?? `Drug #${cellDetail.item.drug_id}`}
              </p>
              <p className="text-xs text-gray-500 mt-1">
                위치: {cellDetail.row + 1}행 {cellDetail.col + 1}열
              </p>
              <p className="text-xs text-gray-500">
                수량: {cellDetail.item.current_quantity}
                {cellDetail.item.min_quantity != null && ` (최소 ${cellDetail.item.min_quantity})`}
              </p>
              {cellDetail.item.is_low_stock && (
                <span className="inline-block mt-1 text-xs bg-red-100 text-red-600 px-1.5 py-0.5 rounded font-medium">
                  재고 부족
                </span>
              )}
            </div>
            <button
              onClick={handleRemoveDrug}
              className="w-full py-2 text-sm font-medium text-red-600 bg-red-50 hover:bg-red-100 rounded-lg transition-colors"
            >
              위치 제거
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}

import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client.ts';
import type {
  OtcItemResponse,
  OtcListResponse,
  ShelfLayoutListResponse,
  ShelfLayoutResponse,
  ShelfPosition,
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
  const [editorDefaultPosition, setEditorDefaultPosition] = useState<ShelfPosition>('front');
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

  function openAddEditor(position: ShelfPosition) {
    setEditLayout(undefined);
    setEditorDefaultPosition(position);
    setEditorOpen(true);
  }

  function openEditEditor(layout: ShelfLayoutResponse) {
    setEditLayout(layout);
    setEditorDefaultPosition(layout.position);
    setEditorOpen(true);
  }

  // Group layouts by position for floorplan
  const frontLayouts = layouts.filter((l) => l.position === 'front');
  const leftLayouts = layouts.filter((l) => l.position === 'left');
  const rightLayouts = layouts.filter((l) => l.position === 'right');

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
            {type === 'DISPLAY' ? '재고' : '창고'}
          </button>
        ))}
      </div>

      {/* === DISPLAY: Floorplan View === */}
      {locationType === 'DISPLAY' && (
        <div className="space-y-2">
          {/* Top row: front cabinets (left) + entrance (center) + empty (right) */}
          <div className="grid grid-cols-3 gap-1.5">
            {/* Front cabinets - left of entrance */}
            <div className="flex flex-col gap-1.5">
              {frontLayouts.map((l) => (
                <CabinetSlot
                  key={l.id}
                  layout={l}
                  isSelected={selectedLayout?.id === l.id}
                  onSelect={() => setSelectedLayout(l)}
                  onEdit={() => openEditEditor(l)}
                />
              ))}
              <AddSlot onClick={() => openAddEditor('front')} />
            </div>
            {/* Entrance - top center */}
            <div className="flex items-start justify-center">
              <div className="w-full h-10 flex items-center justify-center text-[10px] text-gray-400 border border-dashed border-gray-300 rounded bg-gray-50">
                입구
              </div>
            </div>
            {/* Empty space - right of entrance */}
            <div />
          </div>

          {/* Middle: left wall + empty center + right wall */}
          <div className="flex gap-1.5">
            {/* Left column */}
            <div className="flex flex-col gap-1.5 flex-shrink-0">
              {leftLayouts.map((l) => (
                <CabinetSlot
                  key={l.id}
                  layout={l}
                  isSelected={selectedLayout?.id === l.id}
                  onSelect={() => setSelectedLayout(l)}
                  onEdit={() => openEditEditor(l)}
                />
              ))}
              <AddSlot onClick={() => openAddEditor('left')} />
            </div>

            {/* Center empty space */}
            <div className="flex-1 min-h-[120px]" />

            {/* Right column */}
            <div className="flex flex-col gap-1.5 flex-shrink-0">
              {rightLayouts.map((l) => (
                <CabinetSlot
                  key={l.id}
                  layout={l}
                  isSelected={selectedLayout?.id === l.id}
                  onSelect={() => setSelectedLayout(l)}
                  onEdit={() => openEditEditor(l)}
                />
              ))}
              <AddSlot onClick={() => openAddEditor('right')} />
            </div>
          </div>

          {/* Bottom: counter */}
          <div className="flex justify-center">
            <div className="px-6 py-2 text-xs text-gray-400 border border-dashed border-gray-300 rounded-lg bg-gray-50">
              카운터(조제대)
            </div>
          </div>

          {/* Divider + selected layout grid */}
          {selectedLayout && (
            <div className="pt-3 border-t border-gray-200">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-semibold text-gray-700">{selectedLayout.name}</h3>
                <span className="text-xs text-gray-400">
                  {selectedLayout.rows} × {selectedLayout.cols}
                </span>
              </div>
              {loading ? (
                <div className="flex items-center justify-center h-24">
                  <span className="inline-block w-6 h-6 border-3 border-blue-600 border-t-transparent rounded-full animate-spin" />
                </div>
              ) : (
                <ShelfGrid
                  layout={selectedLayout}
                  items={items}
                  onCellClick={handleCellClick}
                />
              )}
            </div>
          )}
        </div>
      )}

      {/* === STORAGE: Simple List View === */}
      {locationType === 'STORAGE' && (
        <div className="space-y-2">
          {/* Layout list */}
          <div className="space-y-2">
            {layouts.map((l) => (
              <button
                key={l.id}
                onClick={() => setSelectedLayout(l)}
                className={`w-full text-left px-4 py-3 rounded-lg border transition-colors ${
                  selectedLayout?.id === l.id
                    ? 'border-blue-300 bg-blue-50'
                    : 'border-gray-200 bg-white hover:bg-gray-50'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-gray-800">{l.name}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-400">{l.rows} × {l.cols}</span>
                    {selectedLayout?.id === l.id && (
                      <span
                        onClick={(e) => { e.stopPropagation(); openEditEditor(l); }}
                        className="text-blue-500 hover:text-blue-700 cursor-pointer text-sm"
                      >
                        &#9998;
                      </span>
                    )}
                  </div>
                </div>
              </button>
            ))}
          </div>

          {/* Add button */}
          <button
            onClick={() => openAddEditor('front')}
            className="w-full py-3 text-sm text-gray-500 bg-gray-50 hover:bg-gray-100 border border-dashed border-gray-300 rounded-lg transition-colors"
          >
            + 약장 추가
          </button>

          {/* Selected layout grid */}
          {selectedLayout ? (
            loading ? (
              <div className="flex items-center justify-center h-24">
                <span className="inline-block w-6 h-6 border-3 border-blue-600 border-t-transparent rounded-full animate-spin" />
              </div>
            ) : (
              <div className="pt-2">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-sm font-semibold text-gray-700">{selectedLayout.name}</h3>
                  <span className="text-xs text-gray-400">
                    {selectedLayout.rows} × {selectedLayout.cols}
                  </span>
                </div>
                <ShelfGrid
                  layout={selectedLayout}
                  items={items}
                  onCellClick={handleCellClick}
                />
              </div>
            )
          ) : (
            <div className="text-center text-sm text-gray-400 py-6">
              {layouts.length === 0 ? '약장을 추가해 주세요' : '약장을 선택해 주세요'}
            </div>
          )}
        </div>
      )}

      {/* Layout Editor Modal */}
      {editorOpen && (
        <ShelfLayoutEditor
          layout={editLayout}
          locationType={locationType}
          defaultPosition={editorDefaultPosition}
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

/* ---- Sub-components ---- */

function CabinetSlot({
  layout,
  isSelected,
  onSelect,
  onEdit,
}: {
  layout: ShelfLayoutResponse;
  isSelected: boolean;
  onSelect: () => void;
  onEdit: () => void;
}) {
  return (
    <button
      onClick={onSelect}
      className={`relative flex-shrink-0 w-20 h-10 flex items-center justify-center text-xs font-medium rounded-lg border transition-colors ${
        isSelected
          ? 'border-blue-400 bg-blue-100 text-blue-700'
          : 'border-gray-300 bg-white text-gray-700 hover:bg-gray-50'
      }`}
    >
      <span className="truncate px-1">{layout.name}</span>
      {isSelected && (
        <span
          onClick={(e) => { e.stopPropagation(); onEdit(); }}
          className="absolute -top-1.5 -right-1.5 w-5 h-5 flex items-center justify-center text-[10px] bg-blue-500 text-white rounded-full hover:bg-blue-600 cursor-pointer"
        >
          &#9998;
        </span>
      )}
    </button>
  );
}

function AddSlot({ onClick }: { onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="flex-shrink-0 w-10 h-10 flex items-center justify-center text-lg text-gray-400 border border-dashed border-gray-300 rounded-lg hover:bg-gray-50 hover:text-gray-600 transition-colors"
    >
      +
    </button>
  );
}

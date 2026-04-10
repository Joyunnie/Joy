import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client.ts';
import PageHeader from '../components/common/PageHeader.tsx';
import type {
  ShelfLayoutListResponse,
  ShelfLayoutResponse,
  ShelfPosition,
} from '../types/api.ts';
import ShelfGrid from '../components/ShelfGrid.tsx';
import ShelfLayoutEditor from '../components/ShelfLayoutEditor.tsx';
import CellDetailView from '../components/CellDetailView.tsx';
import Toast from '../components/Toast.tsx';
import { useToast } from '../hooks/useToast.ts';

type LocationType = 'DISPLAY' | 'STORAGE';

export default function ShelfViewPage() {
  const navigate = useNavigate();
  const { toasts, showToast, removeToast } = useToast();

  const [locationType, setLocationType] = useState<LocationType>('DISPLAY');
  const [layouts, setLayouts] = useState<ShelfLayoutResponse[]>([]);
  const [selectedLayout, setSelectedLayout] = useState<ShelfLayoutResponse | null>(null);
  const [loading, setLoading] = useState(true);

  // modal states
  const [editorOpen, setEditorOpen] = useState(false);
  const [editLayout, setEditLayout] = useState<ShelfLayoutResponse | undefined>(undefined);
  const [editorDefaultPosition, setEditorDefaultPosition] = useState<ShelfPosition>('front');
  const [cellDetailTarget, setCellDetailTarget] = useState<{ row: number; col: number } | null>(null);

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
    } finally {
      setLoading(false);
    }
  }, [locationType, showToast]);

  useEffect(() => { fetchLayouts(); }, [fetchLayouts]);

  const handleCellClick = useCallback((row: number, col: number) => {
    setCellDetailTarget({ row, col });
  }, []);

  const handleCellDrugsSave = useCallback(async (drugs: string[]) => {
    if (!selectedLayout || !cellDetailTarget) return;
    try {
      const { data } = await api.patch<ShelfLayoutResponse>(
        `/shelf-layouts/${selectedLayout.id}/cells/${cellDetailTarget.row}/${cellDetailTarget.col}/drugs`,
        { drugs },
      );
      setSelectedLayout(data);
      setLayouts((prev) => prev.map((l) => (l.id === data.id ? data : l)));
    } catch {
      showToast('약품 저장에 실패했습니다', 'error');
    }
  }, [selectedLayout, cellDetailTarget, showToast]);

  const handleEditorSave = useCallback(() => {
    setEditorOpen(false);
    setEditLayout(undefined);
    showToast('저장되었습니다');
    fetchLayouts();
  }, [showToast, fetchLayouts]);

  const openAddEditor = useCallback((position: ShelfPosition) => {
    setEditLayout(undefined);
    setEditorDefaultPosition(position);
    setEditorOpen(true);
  }, []);

  const openEditEditor = useCallback((layout: ShelfLayoutResponse) => {
    setEditLayout(layout);
    setEditorDefaultPosition(layout.position);
    setEditorOpen(true);
  }, []);

  // Group layouts by position for floorplan
  const { frontLayouts, leftLayouts, rightLayouts } = useMemo(() => ({
    frontLayouts: layouts.filter((l) => l.position === 'front'),
    leftLayouts: layouts.filter((l) => l.position === 'left'),
    rightLayouts: layouts.filter((l) => l.position === 'right'),
  }), [layouts]);

  return (
    <div className="p-4 max-w-lg mx-auto">
      <Toast toasts={toasts} onRemove={removeToast} />

      <PageHeader title="약장 관리" onBack={() => navigate('/inventory')} />

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
        <div className="grid grid-cols-4 gap-1.5">
          {/* Top row: empty corner | front shelves | entrance | empty corner */}
          <div className="flex items-center justify-center">
            <div className="w-full h-10 flex items-center justify-center text-[10px] text-gray-300 border border-dashed border-gray-200 rounded bg-gray-50/50" />
          </div>
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
          <div className="flex items-start justify-center">
            <div className="w-full h-10 flex items-center justify-center text-[10px] text-gray-400 border border-dashed border-gray-300 rounded bg-gray-50">
              입구
            </div>
          </div>
          <div className="flex items-center justify-center">
            <div className="w-full h-10 flex items-center justify-center text-[10px] text-gray-300 border border-dashed border-gray-200 rounded bg-gray-50/50" />
          </div>

          {/* Middle rows: left shelf | empty center (col-span-2) | right shelf */}
          {Array.from({ length: Math.max(leftLayouts.length, rightLayouts.length) }).map((_, i) => (
            <div key={`middle-${i}`} className="contents">
              <div className="flex items-center">
                {leftLayouts[i] ? (
                  <CabinetSlot
                    layout={leftLayouts[i]}
                    isSelected={selectedLayout?.id === leftLayouts[i].id}
                    onSelect={() => setSelectedLayout(leftLayouts[i])}
                    onEdit={() => openEditEditor(leftLayouts[i])}
                  />
                ) : <div className="h-10" />}
              </div>
              <div className="col-span-2" />
              <div className="flex items-center justify-end">
                {rightLayouts[i] ? (
                  <CabinetSlot
                    layout={rightLayouts[i]}
                    isSelected={selectedLayout?.id === rightLayouts[i].id}
                    onSelect={() => setSelectedLayout(rightLayouts[i])}
                    onEdit={() => openEditEditor(rightLayouts[i])}
                  />
                ) : <div className="h-10" />}
              </div>
            </div>
          ))}

          {/* Add buttons row for left / right */}
          <div className="flex items-center">
            <AddSlot onClick={() => openAddEditor('left')} />
          </div>
          <div className="col-span-2" />
          <div className="flex items-center justify-end">
            <AddSlot onClick={() => openAddEditor('right')} />
          </div>

          {/* Bottom: counter full width */}
          <div className="col-span-4">
            <div className="w-full py-2 text-xs text-gray-400 border border-dashed border-gray-300 rounded-lg bg-gray-50 text-center">
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

      {/* Cell Detail View */}
      {cellDetailTarget && selectedLayout && (
        <CellDetailView
          layoutId={selectedLayout.id}
          row={cellDetailTarget.row}
          col={cellDetailTarget.col}
          drugs={selectedLayout.cell_drugs?.[`${cellDetailTarget.row},${cellDetailTarget.col}`] ?? []}
          onSave={handleCellDrugsSave}
          onClose={() => setCellDetailTarget(null)}
        />
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

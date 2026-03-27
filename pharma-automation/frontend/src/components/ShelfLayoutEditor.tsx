import { useState } from 'react';
import api from '../api/client.ts';
import type { ShelfLayoutResponse } from '../types/api.ts';
import Modal from './Modal.tsx';
import ConfirmDialog from './ConfirmDialog.tsx';

interface ShelfLayoutEditorProps {
  layout?: ShelfLayoutResponse;
  locationType: 'DISPLAY' | 'STORAGE';
  onClose: () => void;
  onSave: () => void;
  onError: (msg: string) => void;
}

export default function ShelfLayoutEditor({
  layout,
  locationType,
  onClose,
  onSave,
  onError,
}: ShelfLayoutEditorProps) {
  const [name, setName] = useState(layout?.name ?? '');
  const [rows, setRows] = useState(layout?.rows ?? 4);
  const [cols, setCols] = useState(layout?.cols ?? 6);
  const [saving, setSaving] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);

  async function handleSave() {
    if (!name.trim()) return;
    setSaving(true);
    try {
      if (layout) {
        await api.put(`/shelf-layouts/${layout.id}`, { name, rows, cols });
      } else {
        await api.post('/shelf-layouts', {
          name,
          location_type: locationType,
          rows,
          cols,
        });
      }
      onSave();
    } catch {
      onError(layout ? '수정에 실패했습니다' : '생성에 실패했습니다');
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!layout) return;
    try {
      await api.delete(`/shelf-layouts/${layout.id}`);
      onSave();
    } catch {
      onError('삭제에 실패했습니다');
    }
  }

  return (
    <>
      <Modal isOpen onClose={onClose} title={layout ? '레이아웃 수정' : '레이아웃 추가'}>
        <div className="space-y-3">
          <div>
            <label className="block text-xs text-gray-600 mb-1">이름</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={50}
              placeholder="예: 매장 약장 A"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              autoFocus
            />
          </div>
          <div className="flex gap-3">
            <div className="flex-1">
              <label className="block text-xs text-gray-600 mb-1">행 수 (1~10)</label>
              <input
                type="number"
                min={1}
                max={10}
                value={rows}
                onChange={(e) => setRows(Math.min(10, Math.max(1, Number(e.target.value))))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div className="flex-1">
              <label className="block text-xs text-gray-600 mb-1">열 수 (1~10)</label>
              <input
                type="number"
                min={1}
                max={10}
                value={cols}
                onChange={(e) => setCols(Math.min(10, Math.max(1, Number(e.target.value))))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          {/* Preview grid */}
          <div>
            <p className="text-xs text-gray-500 mb-1">미리보기 ({rows} × {cols})</p>
            <div className="overflow-x-auto border border-gray-200 rounded-lg p-2">
              {Array.from({ length: rows }, (_, r) => (
                <div key={r} className="flex gap-0.5 mb-0.5">
                  {Array.from({ length: cols }, (_, c) => (
                    <div key={c} className="w-6 h-6 border border-dashed border-gray-300 rounded bg-gray-50 flex-shrink-0" />
                  ))}
                </div>
              ))}
            </div>
          </div>

          <button
            onClick={handleSave}
            disabled={saving || !name.trim()}
            className="w-full py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg disabled:opacity-50 transition-colors"
          >
            {saving ? '저장 중...' : '저장'}
          </button>

          {layout && (
            <button
              onClick={() => setDeleteOpen(true)}
              className="w-full py-2 text-sm font-medium text-red-600 bg-red-50 hover:bg-red-100 rounded-lg transition-colors"
            >
              레이아웃 삭제
            </button>
          )}
        </div>
      </Modal>

      <ConfirmDialog
        isOpen={deleteOpen}
        onConfirm={handleDelete}
        onCancel={() => setDeleteOpen(false)}
        title="레이아웃 삭제"
        message={`"${layout?.name ?? ''}" 레이아웃을 삭제하면 배치된 약품 위치도 초기화됩니다. 정말 삭제하시겠습니까?`}
        confirmLabel="삭제"
        confirmColor="red"
      />
    </>
  );
}

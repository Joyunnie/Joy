import { useState } from 'react';
import api from '../api/client.ts';
import type { ShelfLayoutResponse, ShelfPosition } from '../types/api.ts';
import Modal from './Modal.tsx';
import ConfirmDialog from './ConfirmDialog.tsx';

interface ShelfLayoutEditorProps {
  layout?: ShelfLayoutResponse;
  locationType: 'DISPLAY' | 'STORAGE';
  defaultPosition?: ShelfPosition;
  onClose: () => void;
  onSave: () => void;
  onError: (msg: string) => void;
}

function validateRange(value: string): { valid: boolean; num: number } {
  const num = Number(value);
  if (value.trim() === '' || isNaN(num) || !Number.isInteger(num) || num < 1 || num > 10) {
    return { valid: false, num: 0 };
  }
  return { valid: true, num };
}

export default function ShelfLayoutEditor({
  layout,
  locationType,
  defaultPosition = 'front',
  onClose,
  onSave,
  onError,
}: ShelfLayoutEditorProps) {
  const [name, setName] = useState(layout?.name ?? '');
  const position = layout?.position ?? defaultPosition;
  const [rowsStr, setRowsStr] = useState(String(layout?.rows ?? 4));
  const [colsStr, setColsStr] = useState(String(layout?.cols ?? 6));
  const [rowsError, setRowsError] = useState('');
  const [colsError, setColsError] = useState('');
  const [saving, setSaving] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);

  function validateFields(): boolean {
    let ok = true;
    const r = validateRange(rowsStr);
    const c = validateRange(colsStr);
    if (!r.valid) {
      setRowsError('1~10 사이의 숫자를 입력하세요');
      ok = false;
    } else {
      setRowsError('');
    }
    if (!c.valid) {
      setColsError('1~10 사이의 숫자를 입력하세요');
      ok = false;
    } else {
      setColsError('');
    }
    return ok;
  }

  async function handleSave() {
    if (!name.trim()) return;
    if (!validateFields()) return;
    const rows = Number(rowsStr);
    const cols = Number(colsStr);
    setSaving(true);
    try {
      if (layout) {
        await api.put(`/shelf-layouts/${layout.id}`, { name, position, rows, cols });
      } else {
        await api.post('/shelf-layouts', {
          name,
          location_type: locationType,
          position,
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

  const rowsValid = validateRange(rowsStr).valid;
  const colsValid = validateRange(colsStr).valid;
  const previewRows = rowsValid ? Number(rowsStr) : 0;
  const previewCols = colsValid ? Number(colsStr) : 0;

  return (
    <>
      <Modal isOpen onClose={onClose} title={layout ? '약장 수정' : '약장 추가'}>
        <div className="space-y-3">
          <div>
            <label className="block text-xs text-gray-600 mb-1">이름</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={50}
              placeholder="예: 일반약 1"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              autoFocus
            />
          </div>

          <div className="flex gap-3">
            <div className="flex-1">
              <label className="block text-xs text-gray-600 mb-1">행 수 (1~10)</label>
              <input
                type="text"
                inputMode="numeric"
                value={rowsStr}
                onChange={(e) => { setRowsStr(e.target.value); setRowsError(''); }}
                onBlur={() => {
                  const r = validateRange(rowsStr);
                  if (!r.valid) setRowsError('1~10 사이의 숫자를 입력하세요');
                }}
                className={`w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 ${
                  rowsError ? 'border-red-400 focus:ring-red-400' : 'border-gray-300 focus:ring-blue-500'
                }`}
              />
              {rowsError && <p className="text-xs text-red-500 mt-0.5">{rowsError}</p>}
            </div>
            <div className="flex-1">
              <label className="block text-xs text-gray-600 mb-1">열 수 (1~10)</label>
              <input
                type="text"
                inputMode="numeric"
                value={colsStr}
                onChange={(e) => { setColsStr(e.target.value); setColsError(''); }}
                onBlur={() => {
                  const c = validateRange(colsStr);
                  if (!c.valid) setColsError('1~10 사이의 숫자를 입력하세요');
                }}
                className={`w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 ${
                  colsError ? 'border-red-400 focus:ring-red-400' : 'border-gray-300 focus:ring-blue-500'
                }`}
              />
              {colsError && <p className="text-xs text-red-500 mt-0.5">{colsError}</p>}
            </div>
          </div>

          {/* Preview grid */}
          {previewRows > 0 && previewCols > 0 && (
            <div>
              <p className="text-xs text-gray-500 mb-1">미리보기 ({previewRows} × {previewCols})</p>
              <div className="overflow-x-auto border border-gray-200 rounded-lg p-2">
                {Array.from({ length: previewRows }, (_, r) => (
                  <div key={r} className="flex gap-0.5 mb-0.5">
                    {Array.from({ length: previewCols }, (_, c) => (
                      <div key={c} className="w-6 h-6 border border-dashed border-gray-300 rounded bg-gray-50 flex-shrink-0" />
                    ))}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Sticky footer buttons */}
        <div className="sticky bottom-0 bg-white border-t border-gray-200 px-4 py-3 -mx-4 -mb-4 mt-3 space-y-2">
          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="flex-1 py-2 text-sm font-medium text-gray-600 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
            >
              취소
            </button>
            <button
              onClick={handleSave}
              disabled={saving || !name.trim()}
              className="flex-1 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg disabled:opacity-50 transition-colors"
            >
              {saving ? '저장 중...' : layout ? '저장' : '추가'}
            </button>
          </div>

          {layout && (
            <button
              onClick={() => setDeleteOpen(true)}
              className="w-full py-2 text-sm font-medium text-red-600 bg-red-50 hover:bg-red-100 rounded-lg transition-colors"
            >
              약장 삭제
            </button>
          )}
        </div>
      </Modal>

      <ConfirmDialog
        isOpen={deleteOpen}
        onConfirm={handleDelete}
        onCancel={() => setDeleteOpen(false)}
        title="약장 삭제"
        message={`"${layout?.name ?? ''}" 약장을 삭제하면 배치된 약품 위치도 초기화됩니다. 정말 삭제하시겠습니까?`}
        confirmLabel="삭제"
        confirmColor="red"
      />
    </>
  );
}

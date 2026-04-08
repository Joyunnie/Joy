import { useState } from 'react';
import axios from 'axios';
import api from '../api/client.ts';
import type { OtcItemResponse, OtcUpdateRequest } from '../types/api.ts';
import Modal from './Modal.tsx';

interface Props {
  item: OtcItemResponse;
  onClose: () => void;
  onSuccess: () => void;
  onError: (msg: string) => void;
}

export default function OtcEditModal({ item, onClose, onSuccess, onError }: Props) {
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
      if (axios.isAxiosError(err) && err.response?.status === 409) {
        onError('다른 사용자가 수정했습니다. 새로고침하세요.');
        return;
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

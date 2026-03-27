import { useCallback, useEffect, useState } from 'react';
import api from '../api/client.ts';
import type { ConfirmResponse, ReceiptOcrDetailResponse, ReceiptOcrItemOut } from '../types/api.ts';
import Modal from './Modal.tsx';
import ReceiptOcrItemRow from './ReceiptOcrItemRow.tsx';

interface Props {
  recordId: number;
  onClose: () => void;
  onConfirmed: () => void;
  onError: (msg: string) => void;
  showToast: (msg: string, type?: 'success' | 'error') => void;
}

export default function ReceiptDetailModal({ recordId, onClose, onConfirmed, onError, showToast }: Props) {
  const [detail, setDetail] = useState<ReceiptOcrDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [confirming, setConfirming] = useState(false);

  const fetchDetail = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get<ReceiptOcrDetailResponse>(`/receipt-ocr/${recordId}`);
      setDetail(data);
    } catch {
      onError('상세 정보를 불러오지 못했습니다');
    } finally {
      setLoading(false);
    }
  }, [recordId, onError]);

  useEffect(() => { fetchDetail(); }, [fetchDetail]);

  function handleItemUpdated(updated: ReceiptOcrItemOut) {
    if (!detail) return;
    setDetail({
      ...detail,
      items: detail.items.map((i) => (i.id === updated.id ? updated : i)),
    });
  }

  async function handleConfirmAll() {
    if (!detail) return;
    // 전체 항목 확인 처리
    for (const item of detail.items) {
      if (!item.is_confirmed && (item.drug_id || item.confirmed_drug_id)) {
        try {
          await api.put<ReceiptOcrItemOut>(
            `/receipt-ocr/${recordId}/items/${item.id}`,
            { drug_id: item.confirmed_drug_id ?? item.drug_id, quantity: item.confirmed_quantity ?? item.quantity },
          );
        } catch { /* continue */ }
      }
    }
    await fetchDetail();
  }

  async function handleConfirmIntake() {
    setConfirming(true);
    try {
      const { data } = await api.post<ConfirmResponse>(`/receipt-ocr/${recordId}/confirm`);
      showToast(`입고 확정: ${data.confirmed_count}건 반영`);
      onConfirmed();
    } catch (err: unknown) {
      const resp = (err as { response?: { data?: { detail?: string } } }).response;
      onError(resp?.data?.detail ?? '입고 확정에 실패했습니다');
    } finally {
      setConfirming(false);
    }
  }

  const allConfirmed = detail?.items.every((i) => i.is_confirmed) ?? false;
  const isPending = detail?.record.intake_status === 'PENDING';

  return (
    <Modal isOpen onClose={onClose} title="영수증 상세">
      {loading || !detail ? (
        <div className="flex items-center justify-center h-32">
          <span className="inline-block w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : (
        <div className="space-y-3 max-h-[70vh] overflow-y-auto">
          {/* 헤더 정보 */}
          <div className="bg-gray-50 rounded-lg p-3 text-sm space-y-1">
            {detail.record.supplier_name && <p>거래처: <span className="font-medium">{detail.record.supplier_name}</span></p>}
            {detail.record.receipt_date && <p>날짜: {detail.record.receipt_date}</p>}
            {detail.record.receipt_number && <p>번호: {detail.record.receipt_number}</p>}
            {detail.record.total_amount != null && <p>총액: {detail.record.total_amount.toLocaleString()}원</p>}
            <p>상태:
              <span className={`ml-1 font-medium ${
                detail.record.intake_status === 'CONFIRMED' ? 'text-green-600'
                : detail.record.intake_status === 'CANCELLED' ? 'text-red-600'
                : 'text-yellow-600'
              }`}>
                {detail.record.intake_status === 'PENDING' ? '대기' : detail.record.intake_status === 'CONFIRMED' ? '확정' : '취소'}
              </span>
            </p>
          </div>

          {/* 항목 리스트 */}
          <div className="space-y-2">
            {detail.items.map((item) => (
              <ReceiptOcrItemRow
                key={item.id}
                item={item}
                recordId={recordId}
                onUpdated={handleItemUpdated}
                onError={onError}
              />
            ))}
          </div>

          {detail.items.length === 0 && (
            <p className="text-center text-sm text-gray-400 py-4">파싱된 항목이 없습니다</p>
          )}

          {/* 액션 버튼 */}
          {isPending && detail.items.length > 0 && (
            <div className="flex gap-2 pt-2 border-t">
              {!allConfirmed && (
                <button
                  onClick={handleConfirmAll}
                  className="flex-1 py-2 text-sm font-medium text-blue-600 bg-blue-50 hover:bg-blue-100 rounded-lg transition-colors"
                >
                  전체 확인
                </button>
              )}
              <button
                onClick={handleConfirmIntake}
                disabled={confirming || !allConfirmed}
                className="flex-1 py-2 text-sm font-medium text-white bg-green-600 hover:bg-green-700 rounded-lg disabled:opacity-50 transition-colors"
              >
                {confirming ? '처리 중...' : '입고 확정'}
              </button>
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}

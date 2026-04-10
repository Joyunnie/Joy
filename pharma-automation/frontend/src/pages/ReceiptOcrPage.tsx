import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { X } from 'lucide-react';
import api from '../api/client.ts';
import PageHeader from '../components/common/PageHeader.tsx';
import type { ReceiptListResponse, ReceiptOcrRecordOut, ReceiptOcrResponse } from '../types/api.ts';
import Pagination from '../components/Pagination.tsx';
import EmptyState from '../components/EmptyState.tsx';
import Spinner from '../components/Spinner.tsx';
import Toast from '../components/Toast.tsx';
import FileUploadModal from '../components/FileUploadModal.tsx';
import ReceiptDetailModal from '../components/ReceiptDetailModal.tsx';
import { useToast } from '../hooks/useToast.ts';

const LIMIT = 20;

const STATUS_LABELS: Record<string, string> = {
  '': '전체',
  PENDING: '대기',
  CONFIRMED: '확정',
  CANCELLED: '취소',
};

export default function ReceiptOcrPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<ReceiptOcrRecordOut[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const { toasts, showToast, removeToast } = useToast();

  const [uploadOpen, setUploadOpen] = useState(false);
  const [detailId, setDetailId] = useState<number | null>(null);

  const fetchItems = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, unknown> = { limit: LIMIT, offset };
      if (statusFilter) params.status = statusFilter;
      const { data } = await api.get<ReceiptListResponse>('/receipt-ocr', { params });
      setItems(data.items);
      setTotal(data.total);
    } catch {
      showToast('목록을 불러오지 못했습니다', 'error');
    } finally {
      setLoading(false);
    }
  }, [offset, statusFilter, showToast]);

  useEffect(() => { fetchItems(); }, [fetchItems]);

  function handleUploadSuccess(result: ReceiptOcrResponse) {
    setUploadOpen(false);
    if (result.duplicate_warning) {
      showToast(result.duplicate_warning, 'error');
    } else {
      showToast('OCR 처리 완료');
    }
    setDetailId(result.record.id);
    fetchItems();
  }

  async function handleDelete(id: number) {
    try {
      await api.delete(`/receipt-ocr/${id}`);
      showToast('취소되었습니다');
      fetchItems();
    } catch {
      showToast('취소에 실패했습니다', 'error');
    }
  }

  const statusColor = (s: string) =>
    s === 'CONFIRMED' ? 'bg-green-100 text-green-700'
    : s === 'CANCELLED' ? 'bg-red-100 text-red-600'
    : 'bg-yellow-100 text-yellow-700';

  return (
    <div className="p-4 max-w-lg mx-auto">
      <Toast toasts={toasts} onRemove={removeToast} />

      <PageHeader
        title="입고 OCR"
        onBack={() => navigate('/inventory')}
        action={
          <button
            onClick={() => setUploadOpen(true)}
            className="px-3 py-1.5 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors"
          >
            촬영
          </button>
        }
      />

      {/* 상태 필터 */}
      <div className="flex gap-1.5 mb-4">
        {Object.entries(STATUS_LABELS).map(([value, label]) => (
          <button
            key={value}
            onClick={() => { setStatusFilter(value); setOffset(0); }}
            className={`px-2.5 py-1 text-xs rounded-full transition-colors ${
              statusFilter === value
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {loading ? (
        <Spinner />
      ) : items.length === 0 ? (
        <EmptyState message="영수증이 없습니다" />
      ) : (
        <>
          <div className="space-y-2">
            {items.map((rec) => (
              <div
                key={rec.id}
                className="bg-white rounded-lg shadow-sm p-3 border border-gray-100"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1 cursor-pointer" onClick={() => setDetailId(rec.id)}>
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-medium text-gray-800">
                        {rec.supplier_name ?? '거래처 미확인'}
                      </p>
                      <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${statusColor(rec.intake_status)}`}>
                        {STATUS_LABELS[rec.intake_status] ?? rec.intake_status}
                      </span>
                    </div>
                    <div className="mt-1 text-xs text-gray-500 space-y-0.5">
                      {rec.receipt_date && <p>날짜: {rec.receipt_date}</p>}
                      {rec.total_amount != null && <p>총액: {rec.total_amount.toLocaleString()}원</p>}
                      <p>품목: {rec.item_count}건</p>
                    </div>
                    {rec.duplicate_of && (
                      <p className="mt-1 text-xs text-orange-600">중복 의심 (원본 ID: {rec.duplicate_of})</p>
                    )}
                  </div>
                  {rec.intake_status === 'PENDING' && (
                    <button
                      onClick={(e) => { e.stopPropagation(); handleDelete(rec.id); }}
                      className="text-gray-400 hover:text-red-500 ml-2"
                    >
                      <X size={18} />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
          <Pagination total={total} limit={LIMIT} offset={offset} onChange={setOffset} />
        </>
      )}

      {uploadOpen && (
        <FileUploadModal<ReceiptOcrResponse>
          endpoint="/receipt-ocr/upload"
          title="영수증 촬영/업로드"
          onClose={() => setUploadOpen(false)}
          onSuccess={handleUploadSuccess}
          onError={(msg) => showToast(msg, 'error')}
        />
      )}

      {detailId != null && (
        <ReceiptDetailModal
          recordId={detailId}
          onClose={() => setDetailId(null)}
          onConfirmed={() => { setDetailId(null); fetchItems(); }}
          onError={(msg) => showToast(msg, 'error')}
          showToast={showToast}
        />
      )}
    </div>
  );
}

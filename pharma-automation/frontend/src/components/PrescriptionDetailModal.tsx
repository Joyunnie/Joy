import { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import api from '../api/client.ts';
import type { DrugListResponse, DrugOut, PrescriptionConfirmResponse, PrescriptionOcrDetailResponse, PrescriptionOcrDrugOut, RpaCommandOut } from '../types/api.ts';
import Modal from './Modal.tsx';

interface Props {
  recordId: number;
  onClose: () => void;
  onConfirmed: () => void;
  onError: (msg: string) => void;
  showToast: (msg: string, type?: 'success' | 'error') => void;
}

export default function PrescriptionDetailModal({ recordId, onClose, onConfirmed, onError, showToast }: Props) {
  const [detail, setDetail] = useState<PrescriptionOcrDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [confirming, setConfirming] = useState(false);
  const [sendingRpa, setSendingRpa] = useState(false);

  const fetchDetail = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get<PrescriptionOcrDetailResponse>(`/prescription-ocr/${recordId}`);
      setDetail(data);
    } catch {
      onError('상세 정보를 불러오지 못했습니다');
    } finally {
      setLoading(false);
    }
  }, [recordId, onError]);

  useEffect(() => { fetchDetail(); }, [fetchDetail]);

  function handleDrugUpdated(updated: PrescriptionOcrDrugOut) {
    if (!detail) return;
    setDetail({
      ...detail,
      drugs: detail.drugs.map((d) => (d.id === updated.id ? updated : d)),
    });
  }

  async function handleConfirmAll() {
    if (!detail) return;
    for (const drug of detail.drugs) {
      if (!drug.is_confirmed && (drug.drug_id || drug.confirmed_drug_id)) {
        try {
          await api.put<PrescriptionOcrDrugOut>(
            `/prescription-ocr/${recordId}/drugs/${drug.id}`,
            { drug_id: drug.confirmed_drug_id ?? drug.drug_id },
          );
        } catch { /* continue */ }
      }
    }
    await fetchDetail();
  }

  async function handleConfirm() {
    setConfirming(true);
    try {
      const { data } = await api.post<PrescriptionConfirmResponse>(`/prescription-ocr/${recordId}/confirm`);
      showToast(`확인 완료: ${data.confirmed_count}건`);
      onConfirmed();
    } catch (err: unknown) {
      if (axios.isAxiosError(err)) {
        onError(err.response?.data?.detail ?? '확인에 실패했습니다');
      } else {
        onError('확인에 실패했습니다');
      }
    } finally {
      setConfirming(false);
    }
  }

  async function handleSendToPm20() {
    if (!detail) return;
    setSendingRpa(true);
    try {
      await api.post<RpaCommandOut>('/rpa-commands', {
        command_type: 'PRESCRIPTION_INPUT',
        payload: {
          prescription_ocr_record_id: detail.record.id,
          patient_name: detail.record.patient_name,
          patient_dob: detail.record.patient_dob,
          drugs: detail.drugs.map((d) => ({
            drug_name: d.matched_drug_name ?? d.drug_name_raw,
            dosage: d.confirmed_dosage ?? d.dosage,
            frequency: d.confirmed_frequency ?? d.frequency,
            days: d.confirmed_days ?? d.days,
          })),
        },
      });
      showToast('PM+20 입력 요청이 전송되었습니다');
    } catch {
      onError('PM+20 입력 요청에 실패했습니다');
    } finally {
      setSendingRpa(false);
    }
  }

  const allConfirmed = detail?.drugs.every((d) => d.is_confirmed) ?? false;
  const isCompleted = detail?.record.ocr_status === 'COMPLETED';
  const isConfirmed = detail?.record.ocr_status === 'CONFIRMED';

  return (
    <Modal isOpen onClose={onClose} title="처방전 상세">
      {loading || !detail ? (
        <div className="flex items-center justify-center h-32">
          <span className="inline-block w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : (
        <div className="space-y-3 max-h-[70vh] overflow-y-auto">
          {/* 헤더 정보 */}
          <div className="bg-gray-50 rounded-lg p-3 text-sm space-y-1">
            {detail.record.patient_name && <p>환자: <span className="font-medium">{detail.record.patient_name}</span></p>}
            {detail.record.patient_dob && <p>생년월일: {detail.record.patient_dob}</p>}
            {detail.record.insurance_type && <p>보험: {detail.record.insurance_type}</p>}
            {detail.record.prescriber_name && <p>처방의: {detail.record.prescriber_name}</p>}
            {detail.record.prescriber_clinic && <p>의료기관: {detail.record.prescriber_clinic}</p>}
            {detail.record.prescription_date && <p>처방일: {detail.record.prescription_date}</p>}
            {detail.record.prescription_number && <p>교부번호: {detail.record.prescription_number}</p>}
            <p>상태:
              <span className={`ml-1 font-medium ${
                detail.record.ocr_status === 'CONFIRMED' ? 'text-green-600'
                : detail.record.ocr_status === 'CANCELLED' ? 'text-red-600'
                : 'text-yellow-600'
              }`}>
                {detail.record.ocr_status === 'COMPLETED' ? '대기' : detail.record.ocr_status === 'CONFIRMED' ? '확정' : detail.record.ocr_status}
              </span>
            </p>
          </div>

          {/* 약품 리스트 */}
          <div className="space-y-2">
            {detail.drugs.map((drug) => (
              <PrescriptionDrugRow
                key={drug.id}
                drug={drug}
                recordId={recordId}
                onUpdated={handleDrugUpdated}
                onError={onError}
              />
            ))}
          </div>

          {detail.drugs.length === 0 && (
            <p className="text-center text-sm text-gray-400 py-4">파싱된 약품이 없습니다</p>
          )}

          {/* 액션 버튼 */}
          {isCompleted && detail.drugs.length > 0 && (
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
                onClick={handleConfirm}
                disabled={confirming || !allConfirmed}
                className="flex-1 py-2 text-sm font-medium text-white bg-green-600 hover:bg-green-700 rounded-lg disabled:opacity-50 transition-colors"
              >
                {confirming ? '처리 중...' : '확인 완료'}
              </button>
            </div>
          )}

          {isConfirmed && detail.drugs.length > 0 && (
            <div className="pt-2 border-t">
              <button
                onClick={handleSendToPm20}
                disabled={sendingRpa}
                className="w-full py-2 text-sm font-medium text-white bg-purple-600 hover:bg-purple-700 rounded-lg disabled:opacity-50 transition-colors"
              >
                {sendingRpa ? '전송 중...' : 'PM+20 입력'}
              </button>
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}


// --- Inline drug row component ---

function PrescriptionDrugRow({
  drug,
  recordId,
  onUpdated,
  onError,
}: {
  drug: PrescriptionOcrDrugOut;
  recordId: number;
  onUpdated: (updated: PrescriptionOcrDrugOut) => void;
  onError: (msg: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [drugSearch, setDrugSearch] = useState('');
  const [drugResults, setDrugResults] = useState<DrugOut[]>([]);
  const [dosage, setDosage] = useState(drug.confirmed_dosage ?? drug.dosage ?? '');
  const [frequency, setFrequency] = useState(drug.confirmed_frequency ?? drug.frequency ?? '');
  const [days, setDays] = useState(drug.confirmed_days ?? drug.days ?? 0);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (drugSearch.length < 1) { setDrugResults([]); return; }
    const timer = setTimeout(async () => {
      try {
        const { data } = await api.get<DrugListResponse>('/drugs', { params: { search: drugSearch, limit: 10 } });
        setDrugResults(data.items);
      } catch { /* ignore */ }
    }, 300);
    return () => clearTimeout(timer);
  }, [drugSearch]);

  async function handleSelectDrug(d: DrugOut) {
    setSaving(true);
    try {
      const { data } = await api.put<PrescriptionOcrDrugOut>(
        `/prescription-ocr/${recordId}/drugs/${drug.id}`,
        { drug_id: d.id, dosage, frequency, days: days || undefined },
      );
      onUpdated(data);
      setEditing(false);
    } catch {
      onError('항목 수정에 실패했습니다');
    } finally {
      setSaving(false);
    }
  }

  async function handleConfirmOnly() {
    setSaving(true);
    try {
      const { data } = await api.put<PrescriptionOcrDrugOut>(
        `/prescription-ocr/${recordId}/drugs/${drug.id}`,
        {
          drug_id: drug.confirmed_drug_id ?? drug.drug_id,
          dosage: dosage || undefined,
          frequency: frequency || undefined,
          days: days || undefined,
        },
      );
      onUpdated(data);
    } catch {
      onError('확인에 실패했습니다');
    } finally {
      setSaving(false);
    }
  }

  const scoreColor = (drug.match_score ?? 0) >= 0.7
    ? 'text-green-600'
    : (drug.match_score ?? 0) >= 0.4
      ? 'text-yellow-600'
      : 'text-red-600';

  return (
    <div className={`bg-white rounded-lg border p-3 ${drug.is_confirmed ? 'border-green-200' : 'border-gray-200'}`}>
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="text-sm font-medium text-gray-800">{drug.drug_name_raw ?? '-'}</p>
          <div className="mt-1 flex items-center gap-2 text-xs text-gray-500 flex-wrap">
            <span>투약량: {drug.confirmed_dosage ?? drug.dosage ?? '-'}</span>
            <span>횟수: {drug.confirmed_frequency ?? drug.frequency ?? '-'}</span>
            <span>일수: {drug.confirmed_days ?? drug.days ?? '-'}</span>
            {drug.is_narcotic && <span className="text-red-600 font-medium">마약류</span>}
          </div>
          {drug.matched_drug_name && (
            <div className="mt-1 flex items-center gap-1.5">
              <span className="text-xs text-gray-600">매칭: {drug.matched_drug_name}</span>
              <span className={`text-xs font-medium ${scoreColor}`}>
                ({((drug.match_score ?? 0) * 100).toFixed(0)}%)
              </span>
            </div>
          )}
          {!drug.matched_drug_name && !drug.drug_id && (
            <p className="mt-1 text-xs text-red-500">매칭 실패 - 수동 선택 필요</p>
          )}
        </div>
        <div className="flex items-center gap-1 ml-2">
          {drug.is_confirmed && (
            <span className="text-xs bg-green-100 text-green-700 px-1.5 py-0.5 rounded">확인</span>
          )}
          <button
            onClick={() => setEditing(!editing)}
            className="text-xs text-blue-600 hover:text-blue-800 px-1.5 py-0.5"
          >
            수정
          </button>
          {!drug.is_confirmed && (drug.drug_id || drug.confirmed_drug_id) && (
            <button
              onClick={handleConfirmOnly}
              disabled={saving}
              className="text-xs text-green-600 hover:text-green-800 px-1.5 py-0.5 disabled:opacity-50"
            >
              확인
            </button>
          )}
        </div>
      </div>

      {editing && (
        <div className="mt-2 border-t pt-2 space-y-2">
          <div className="grid grid-cols-3 gap-2">
            <div>
              <label className="block text-xs text-gray-500 mb-1">투약량</label>
              <input
                type="text"
                value={dosage}
                onChange={(e) => setDosage(e.target.value)}
                className="w-full px-2 py-1 border border-gray-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">횟수</label>
              <input
                type="text"
                value={frequency}
                onChange={(e) => setFrequency(e.target.value)}
                className="w-full px-2 py-1 border border-gray-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">일수</label>
              <input
                type="number"
                min={0}
                value={days}
                onChange={(e) => setDays(Number(e.target.value))}
                className="w-full px-2 py-1 border border-gray-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">약품 검색</label>
            <input
              type="text"
              value={drugSearch}
              onChange={(e) => setDrugSearch(e.target.value)}
              placeholder="약품명 검색..."
              className="w-full px-2 py-1 border border-gray-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
            {drugResults.length > 0 && (
              <div className="max-h-32 overflow-y-auto border border-gray-200 rounded mt-1">
                {drugResults.map((d) => (
                  <button
                    key={d.id}
                    onClick={() => handleSelectDrug(d)}
                    disabled={saving}
                    className="w-full text-left px-2 py-1.5 text-xs hover:bg-blue-50 border-b border-gray-100 last:border-b-0 disabled:opacity-50"
                  >
                    <span className="font-medium">{d.name}</span>
                    <span className="text-gray-400 ml-1">{d.standard_code}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

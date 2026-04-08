import type { PrescriptionOcrResponse } from '../types/api.ts';
import FileUploadModal from './FileUploadModal.tsx';

interface Props {
  onClose: () => void;
  onSuccess: (result: PrescriptionOcrResponse) => void;
  onError: (msg: string) => void;
}

export default function PrescriptionUploadModal({ onClose, onSuccess, onError }: Props) {
  return (
    <FileUploadModal<PrescriptionOcrResponse>
      endpoint="/prescription-ocr/upload"
      title="처방전 촬영/업로드"
      onClose={onClose}
      onSuccess={onSuccess}
      onError={onError}
    />
  );
}

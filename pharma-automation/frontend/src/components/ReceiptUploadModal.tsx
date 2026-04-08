import type { ReceiptOcrResponse } from '../types/api.ts';
import FileUploadModal from './FileUploadModal.tsx';

interface Props {
  onClose: () => void;
  onSuccess: (result: ReceiptOcrResponse) => void;
  onError: (msg: string) => void;
}

export default function ReceiptUploadModal({ onClose, onSuccess, onError }: Props) {
  return (
    <FileUploadModal<ReceiptOcrResponse>
      endpoint="/receipt-ocr/upload"
      title="영수증 촬영/업로드"
      onClose={onClose}
      onSuccess={onSuccess}
      onError={onError}
    />
  );
}

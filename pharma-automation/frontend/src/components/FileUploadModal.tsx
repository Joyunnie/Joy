import { useRef, useState } from 'react';
import { X } from 'lucide-react';
import axios from 'axios';
import api from '../api/client.ts';
import Modal from './Modal.tsx';

interface Props<T> {
  endpoint: string;
  title: string;
  onClose: () => void;
  onSuccess: (result: T) => void;
  onError: (msg: string) => void;
}

export default function FileUploadModal<T>({ endpoint, title, onClose, onSuccess, onError }: Props<T>) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;

    if (!['image/jpeg', 'image/png'].includes(f.type)) {
      onError('JPEG 또는 PNG 파일만 지원합니다');
      return;
    }
    if (f.size > 10 * 1024 * 1024) {
      onError('파일 크기가 10MB를 초과합니다');
      return;
    }

    setFile(f);
    const reader = new FileReader();
    reader.onload = () => setPreview(reader.result as string);
    reader.readAsDataURL(f);
  }

  async function handleUpload() {
    if (!file) return;
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const { data } = await api.post<T>(endpoint, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      onSuccess(data);
    } catch (err: unknown) {
      if (axios.isAxiosError(err)) {
        if (err.response?.status === 503) {
          onError('OCR 서비스를 사용할 수 없습니다');
        } else {
          onError(err.response?.data?.detail ?? '업로드에 실패했습니다');
        }
      } else {
        onError('업로드에 실패했습니다');
      }
    } finally {
      setUploading(false);
    }
  }

  return (
    <Modal isOpen onClose={onClose} title={title}>
      <div className="space-y-3">
        <input
          ref={fileRef}
          type="file"
          accept="image/jpeg,image/png"
          capture="environment"
          onChange={handleFileChange}
          className="hidden"
        />

        {preview ? (
          <div className="relative">
            <img src={preview} alt="미리보기" className="w-full max-h-60 object-contain rounded-lg border border-gray-200" />
            <button
              onClick={() => { setPreview(null); setFile(null); }}
              className="absolute top-1 right-1 bg-white/80 rounded-full w-6 h-6 flex items-center justify-center text-gray-600 hover:text-red-500"
            >
              <X size={14} />
            </button>
          </div>
        ) : (
          <button
            onClick={() => fileRef.current?.click()}
            className="w-full py-12 border-2 border-dashed border-gray-300 rounded-lg text-gray-400 hover:border-blue-400 hover:text-blue-500 transition-colors"
          >
            <p className="text-sm font-medium">촬영 또는 파일 선택</p>
            <p className="text-xs mt-1">JPEG, PNG (최대 10MB)</p>
          </button>
        )}

        {file && (
          <button
            onClick={handleUpload}
            disabled={uploading}
            className="w-full py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg disabled:opacity-50 transition-colors"
          >
            {uploading ? (
              <span className="flex items-center justify-center gap-2">
                <span className="inline-block w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                OCR 처리 중...
              </span>
            ) : '업로드'}
          </button>
        )}
      </div>
    </Modal>
  );
}

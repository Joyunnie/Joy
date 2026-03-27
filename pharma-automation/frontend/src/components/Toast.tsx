import type { ToastState } from '../hooks/useToast.ts';

interface ToastProps {
  toasts: ToastState[];
  onRemove: (id: number) => void;
}

export default function Toast({ toasts, onRemove }: ToastProps) {
  if (toasts.length === 0) return null;

  return (
    <div className="fixed top-4 left-1/2 -translate-x-1/2 z-[60] space-y-2 w-[90%] max-w-sm">
      {toasts.map((t) => (
        <div
          key={t.id}
          onClick={() => onRemove(t.id)}
          className={`px-4 py-3 rounded-lg shadow-lg text-sm text-white cursor-pointer ${
            t.type === 'success' ? 'bg-green-600' : 'bg-red-600'
          }`}
        >
          {t.message}
        </div>
      ))}
    </div>
  );
}

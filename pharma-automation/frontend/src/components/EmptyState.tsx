import { Inbox } from 'lucide-react';

interface EmptyStateProps {
  message?: string;
}

export default function EmptyState({ message = '데이터가 없습니다' }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-gray-400">
      <Inbox size={48} strokeWidth={1} className="text-gray-300 mb-3" />
      <p className="text-sm">{message}</p>
    </div>
  );
}

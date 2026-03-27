interface EmptyStateProps {
  message?: string;
}

export default function EmptyState({ message = '데이터가 없습니다' }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-gray-400">
      <span className="text-4xl mb-3">&#x1F4ED;</span>
      <p className="text-sm">{message}</p>
    </div>
  );
}

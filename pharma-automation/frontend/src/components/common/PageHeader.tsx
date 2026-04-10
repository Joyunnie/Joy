import type { ReactNode } from 'react';
import { ArrowLeft } from 'lucide-react';

interface PageHeaderProps {
  title: string;
  onBack?: () => void;
  action?: ReactNode;
}

export default function PageHeader({ title, onBack, action }: PageHeaderProps) {
  return (
    <div className="flex items-center justify-between mb-4">
      <div className="flex items-center gap-2">
        {onBack && (
          <button onClick={onBack} className="text-gray-500 hover:text-gray-700">
            <ArrowLeft size={20} />
          </button>
        )}
        <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
      </div>
      {action && <div>{action}</div>}
    </div>
  );
}

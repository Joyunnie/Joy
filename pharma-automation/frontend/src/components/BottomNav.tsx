import { Link, useLocation } from 'react-router-dom';

const tabs = [
  { path: '/', label: '대시보드', icon: '📊' },
  { path: '/prescription-ocr', label: '처방전', icon: '📋' },
  { path: '/inventory', label: '재고', icon: '📦' },
  { path: '/todos', label: '할일', icon: '✅' },
  { path: '/predictions', label: '내원예측', icon: '📅' },
  { path: '/alerts', label: '알림', icon: '🔔' },
] as const;

export default function BottomNav() {
  const { pathname } = useLocation();

  return (
    <nav className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 z-50">
      <div className="flex justify-around items-center h-14 max-w-lg mx-auto">
        {tabs.map((tab) => {
          const isActive = pathname === tab.path;
          return (
            <Link
              key={tab.path}
              to={tab.path}
              className={`flex-1 flex flex-col items-center py-1.5 text-[10px] font-medium transition-colors ${
                isActive
                  ? 'text-blue-600'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              <span className="text-base leading-none mb-0.5">{tab.icon}</span>
              {tab.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}

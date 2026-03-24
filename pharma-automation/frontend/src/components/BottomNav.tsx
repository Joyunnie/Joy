import { Link, useLocation } from 'react-router-dom';

const tabs = [
  { path: '/', label: '대시보드' },
  { path: '/inventory', label: '재고' },
  { path: '/narcotics', label: '마약류' },
  { path: '/alerts', label: '알림' },
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
              className={`flex-1 text-center py-2 text-sm font-medium transition-colors ${
                isActive
                  ? 'text-blue-600'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              {tab.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}

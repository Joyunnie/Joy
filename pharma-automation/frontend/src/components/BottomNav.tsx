import { Link, useLocation } from 'react-router-dom';
import { LayoutDashboard, Pill, Package, CheckSquare, Calendar, Bell } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

const tabs: { path: string; label: string; Icon: LucideIcon }[] = [
  { path: '/', label: '대시보드', Icon: LayoutDashboard },
  { path: '/canisters', label: '캐니스터', Icon: Pill },
  { path: '/inventory', label: '재고', Icon: Package },
  { path: '/todos', label: '할일', Icon: CheckSquare },
  { path: '/predictions', label: '내원예측', Icon: Calendar },
  { path: '/alerts', label: '알림', Icon: Bell },
];

export default function BottomNav() {
  const { pathname } = useLocation();

  return (
    <nav className="fixed bottom-0 left-0 right-0 bg-white/90 backdrop-blur-md border-t border-gray-200 z-50 pb-[env(safe-area-inset-bottom)]">
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
                  : 'text-gray-400'
              }`}
            >
              <tab.Icon size={20} strokeWidth={1.5} className="mb-0.5" />
              {tab.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}

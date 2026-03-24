import { Outlet } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext.tsx';
import BottomNav from './BottomNav.tsx';

export default function Layout() {
  const { username, role, logout } = useAuth();

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Header */}
      <header className="sticky top-0 z-40 bg-blue-600 text-white px-4 py-3 flex items-center justify-between shadow-sm">
        <h1 className="text-lg font-bold">약국관리</h1>
        <div className="flex items-center gap-3">
          <span className="text-sm opacity-90">
            {username ?? role ?? ''}
          </span>
          <button
            onClick={logout}
            className="text-sm bg-blue-700 hover:bg-blue-800 px-3 py-1 rounded transition-colors"
          >
            로그아웃
          </button>
        </div>
      </header>

      {/* Content */}
      <main className="flex-1 pb-16">
        <Outlet />
      </main>

      {/* Bottom Navigation */}
      <BottomNav />
    </div>
  );
}

import { useLocation } from 'react-router-dom';

const titles: Record<string, string> = {
  '/inventory': '재고 관리',
  '/narcotics': '마약류 관리',
  '/alerts': '알림',
};

export default function PlaceholderPage() {
  const { pathname } = useLocation();
  const title = titles[pathname] ?? '페이지';

  return (
    <div className="flex flex-col items-center justify-center h-64 text-gray-400">
      <p className="text-lg font-medium">{title}</p>
      <p className="text-sm mt-1">Phase 3B에서 구현 예정</p>
    </div>
  );
}

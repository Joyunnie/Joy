interface PaginationProps {
  total: number;
  limit: number;
  offset: number;
  onChange: (offset: number) => void;
}

export default function Pagination({ total, limit, offset, onChange }: PaginationProps) {
  if (total <= limit) return null;

  const totalPages = Math.ceil(total / limit);
  const currentPage = Math.floor(offset / limit) + 1;

  function goTo(page: number) {
    onChange((page - 1) * limit);
  }

  const pages: (number | '...')[] = [];
  for (let i = 1; i <= totalPages; i++) {
    if (i === 1 || i === totalPages || (i >= currentPage - 1 && i <= currentPage + 1)) {
      pages.push(i);
    } else if (pages[pages.length - 1] !== '...') {
      pages.push('...');
    }
  }

  return (
    <div className="flex items-center justify-between py-3">
      <span className="text-xs text-gray-500">전체 {total}건</span>
      <div className="flex items-center gap-1">
        <button
          onClick={() => goTo(currentPage - 1)}
          disabled={currentPage === 1}
          className="px-2 py-1 text-xs rounded border border-gray-300 disabled:opacity-30 hover:bg-gray-100"
        >
          이전
        </button>
        {pages.map((p, idx) =>
          p === '...' ? (
            <span key={`dot-${idx}`} className="px-1 text-xs text-gray-400">...</span>
          ) : (
            <button
              key={p}
              onClick={() => goTo(p)}
              className={`px-2 py-1 text-xs rounded border ${
                p === currentPage
                  ? 'bg-blue-600 text-white border-blue-600'
                  : 'border-gray-300 hover:bg-gray-100'
              }`}
            >
              {p}
            </button>
          ),
        )}
        <button
          onClick={() => goTo(currentPage + 1)}
          disabled={currentPage === totalPages}
          className="px-2 py-1 text-xs rounded border border-gray-300 disabled:opacity-30 hover:bg-gray-100"
        >
          다음
        </button>
      </div>
    </div>
  );
}

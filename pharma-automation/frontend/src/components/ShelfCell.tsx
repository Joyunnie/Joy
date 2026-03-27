import type { OtcItemResponse } from '../types/api.ts';

interface ShelfCellProps {
  row: number;
  col: number;
  item?: OtcItemResponse;
  onClick: () => void;
}

export default function ShelfCell({ item, onClick }: ShelfCellProps) {
  if (!item) {
    return (
      <button
        onClick={onClick}
        className="w-full aspect-square border border-dashed border-gray-300 rounded bg-gray-50 hover:bg-gray-100 flex items-center justify-center text-gray-400 text-lg transition-colors"
      >
        +
      </button>
    );
  }

  return (
    <button
      onClick={onClick}
      className={`w-full aspect-square border rounded p-1 flex items-center justify-center text-center transition-colors ${
        item.is_low_stock
          ? 'border-red-300 bg-red-50 hover:bg-red-100'
          : 'border-blue-200 bg-blue-50 hover:bg-blue-100'
      }`}
    >
      <span className="text-xs leading-tight line-clamp-2 text-gray-800">
        {item.drug_name ?? `#${item.drug_id}`}
      </span>
    </button>
  );
}

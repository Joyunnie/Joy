import type { OtcItemResponse, ShelfLayoutResponse } from '../types/api.ts';
import { parseLocation } from '../utils/location.ts';
import ShelfCell from './ShelfCell.tsx';

interface ShelfGridProps {
  layout: ShelfLayoutResponse;
  items: OtcItemResponse[];
  onCellClick: (row: number, col: number, item?: OtcItemResponse) => void;
}

export default function ShelfGrid({ layout, items, onCellClick }: ShelfGridProps) {
  // Build a map of (row, col) -> item
  const cellMap = new Map<string, OtcItemResponse>();
  const locField = layout.location_type === 'DISPLAY' ? 'display_location' : 'storage_location';

  for (const item of items) {
    const loc = parseLocation(item[locField]);
    if (loc && loc.layoutId === layout.id) {
      cellMap.set(`${loc.row},${loc.col}`, item);
    }
  }

  return (
    <div className="overflow-x-auto">
      <div className="min-w-fit">
        {/* Column headers */}
        <div
          className="grid gap-1 mb-1"
          style={{ gridTemplateColumns: `24px repeat(${layout.cols}, minmax(60px, 1fr))` }}
        >
          <div />
          {Array.from({ length: layout.cols }, (_, c) => (
            <div key={c} className="text-center text-xs text-gray-400 font-medium">
              {c + 1}
            </div>
          ))}
        </div>

        {/* Grid rows */}
        {Array.from({ length: layout.rows }, (_, r) => (
          <div
            key={r}
            className="grid gap-1 mb-1"
            style={{ gridTemplateColumns: `24px repeat(${layout.cols}, minmax(60px, 1fr))` }}
          >
            {/* Row header */}
            <div className="flex items-center justify-center text-xs text-gray-400 font-medium">
              {r + 1}
            </div>
            {/* Cells */}
            {Array.from({ length: layout.cols }, (_, c) => {
              const item = cellMap.get(`${r},${c}`);
              return (
                <ShelfCell
                  key={c}
                  row={r}
                  col={c}
                  item={item}
                  onClick={() => onCellClick(r, c, item)}
                />
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}

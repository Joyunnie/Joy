import type { ShelfLayoutResponse } from '../types/api.ts';
import ShelfCell from './ShelfCell.tsx';

interface ShelfGridProps {
  layout: ShelfLayoutResponse;
  onCellClick: (row: number, col: number) => void;
}

export default function ShelfGrid({ layout, onCellClick }: ShelfGridProps) {
  const cellDrugs = layout.cell_drugs ?? {};

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
              const drugs = cellDrugs[`${r},${c}`] ?? [];
              return (
                <ShelfCell
                  key={c}
                  row={r}
                  col={c}
                  drugs={drugs}
                  onClick={() => onCellClick(r, c)}
                />
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}

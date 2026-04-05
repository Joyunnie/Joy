interface ShelfCellProps {
  row: number;
  col: number;
  drugs: string[];
  onClick: () => void;
}

export default function ShelfCell({ drugs, onClick }: ShelfCellProps) {
  if (drugs.length === 0) {
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
      className="w-full aspect-square border border-blue-200 bg-blue-50 hover:bg-blue-100 rounded p-1 flex flex-col items-center justify-center text-center transition-colors"
    >
      <span className="text-xs leading-tight line-clamp-2 text-gray-800">
        {drugs[0]}
      </span>
      {drugs.length > 1 && (
        <span className="text-[10px] text-blue-500 mt-0.5">
          +{drugs.length - 1}
        </span>
      )}
    </button>
  );
}

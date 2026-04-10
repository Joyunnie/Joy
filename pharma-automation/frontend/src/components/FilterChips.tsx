interface FilterChip<T extends string | number> {
  value: T;
  label: string;
}

interface FilterChipsProps<T extends string | number> {
  options: readonly FilterChip<T>[];
  value: T;
  onChange: (value: T) => void;
  /** Extra Tailwind classes for the wrapper div. */
  className?: string;
}

/** Horizontally scrollable row of pill-shaped filter chips. */
export default function FilterChips<T extends string | number>({
  options,
  value,
  onChange,
  className = '',
}: FilterChipsProps<T>) {
  return (
    <div className={`flex gap-2 overflow-x-auto pb-2 scrollbar-hide ${className}`}>
      {options.map((opt) => (
        <button
          key={String(opt.value)}
          onClick={() => onChange(opt.value)}
          className={`px-3 py-1 text-xs font-medium rounded-full whitespace-nowrap transition-colors ${
            opt.value === value
              ? 'bg-blue-600 text-white'
              : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

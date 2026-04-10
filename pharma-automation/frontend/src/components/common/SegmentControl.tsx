interface SegmentOption<T extends string> {
  value: T;
  label: string;
}

interface SegmentControlProps<T extends string> {
  options: SegmentOption<T>[];
  value: T;
  onChange: (value: T) => void;
}

export default function SegmentControl<T extends string>({
  options,
  value,
  onChange,
}: SegmentControlProps<T>) {
  return (
    <div className="flex bg-gray-100 rounded-lg p-1 mb-4" role="tablist">
      {options.map((opt) => (
        <button
          key={opt.value}
          role="tab"
          aria-selected={value === opt.value}
          onClick={() => onChange(opt.value)}
          className={`flex-1 text-center py-1.5 text-sm rounded-md transition-colors duration-150 ${
            value === opt.value
              ? 'bg-white shadow-sm font-semibold text-gray-900'
              : 'text-gray-500'
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

import { getCategoryItems } from '../data/foodData';

export default function SlotRow({ slotDef, dropdown, amount, onDropdownChange, onAmountChange }) {
  const items = slotDef.category === 'water'
    ? [{ index: 2, name: '물' }]
    : getCategoryItems(slotDef.category);

  return (
    <div className="flex items-center gap-1 mb-0.5">
      <select
        className="flex-1 min-w-0 text-xs border border-gray-300 rounded px-1 py-0.5 bg-white truncate"
        value={dropdown || 0}
        onChange={(e) => onDropdownChange(Number(e.target.value))}
      >
        <option value={0}>선택</option>
        {items.map((item) => (
          <option key={item.index} value={item.index}>
            {item.name}
          </option>
        ))}
      </select>
      <input
        type="number"
        className="w-16 text-xs border border-gray-300 rounded px-1 py-0.5 text-right"
        value={amount || ''}
        onChange={(e) => onAmountChange(e.target.value === '' ? '' : Number(e.target.value))}
        min={0}
        step="any"
        placeholder="0"
      />
      <span className="text-xs text-gray-500 w-6">{slotDef.unit}</span>
    </div>
  );
}

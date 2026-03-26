import { getCategoryItems } from '../data/foodData';

export default function SlotRow({ slotDef, dropdown, amount, onDropdownChange, onAmountChange }) {
  const items = slotDef.category === 'water'
    ? [{ index: 2, name: '물' }]
    : getCategoryItems(slotDef.category);

  // Dynamic unit: use selected item's unit if available (for merged categories)
  const selectedItem = items.find(i => i.index === (dropdown || 0));
  const displayUnit = selectedItem?.unit || slotDef.unit;

  return (
    <div className="flex items-center gap-0.5">
      <select
        className="flex-1 min-w-0 text-[10px] border border-gray-300 rounded px-0.5 py-0 h-5 bg-white truncate"
        value={dropdown || 0}
        onChange={(e) => onDropdownChange(Number(e.target.value))}
      >
        <option value={0}>선택</option>
        {items.map((item) => (
          <option key={item.index} value={item.index}>{item.label || item.name}</option>
        ))}
      </select>
      <input
        type="number"
        className="w-14 text-[10px] border border-gray-300 rounded px-0.5 py-0 h-5 text-right"
        value={amount || ''}
        onChange={(e) => onAmountChange(e.target.value === '' ? '' : Number(e.target.value))}
        min={0}
        step="any"
        placeholder="0"
      />
      <span className="text-[9px] text-gray-400 w-5">{displayUnit}</span>
    </div>
  );
}

const fields = [
  { key: 'protein', label: '단백질 DM%' },
  { key: 'fat', label: '지방 DM%' },
  { key: 'calcium', label: '칼슘 DM%' },
  { key: 'phosphorus', label: '인 DM%' },
  { key: 'sodium', label: '나트륨 DM%' },
];

export default function NutrientAdjust({ values, onUpdate, onReset }) {
  return (
    <div className="bg-white rounded-lg p-3 shadow-sm border">
      <div className="flex justify-between items-center mb-2">
        <h3 className="font-bold text-sm text-gray-800">특정영양소 조절</h3>
        <button
          onClick={onReset}
          className="text-xs px-2 py-0.5 bg-gray-200 rounded hover:bg-gray-300"
        >
          리셋
        </button>
      </div>
      <p className="text-xs text-gray-500 mb-1">DM% 기준 (0이면 비활성)</p>
      <div className="space-y-1">
        {fields.map(({ key, label }) => (
          <div key={key} className="flex items-center gap-1">
            <label className="text-xs w-20 shrink-0">{label}</label>
            <input
              type="number"
              className="w-20 text-xs border border-gray-300 rounded px-1 py-0.5 text-right"
              value={values[key] || ''}
              onChange={(e) => onUpdate({ [key]: e.target.value === '' ? '' : Number(e.target.value) })}
              min={0}
              step="any"
            />
          </div>
        ))}
      </div>
    </div>
  );
}

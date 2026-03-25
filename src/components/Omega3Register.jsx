const fields = [
  { key: 'calories', label: '칼로리', unit: 'Kcal' },
  { key: 'fat', label: '지방', unit: 'g' },
  { key: 'epa', label: 'EPA', unit: 'mg' },
  { key: 'dha', label: 'DHA', unit: 'mg' },
  { key: 'otherOmega3', label: '기타오메가3', unit: 'mg' },
  { key: 'vitE', label: '비타민E', unit: 'mg' },
];

export default function Omega3Register({ values, onUpdate, onReset }) {
  return (
    <div className="bg-white rounded-lg p-3 shadow-sm border">
      <div className="flex justify-between items-center mb-2">
        <h3 className="font-bold text-sm text-gray-800">나의 오메가3 영양제 등록</h3>
        <button
          onClick={onReset}
          className="text-xs px-2 py-0.5 bg-gray-200 rounded hover:bg-gray-300"
        >
          리셋
        </button>
      </div>
      <div className="space-y-1">
        {fields.map(({ key, label, unit }) => (
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
            <span className="text-xs text-gray-500">{unit}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

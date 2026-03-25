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
    <div className="bg-white rounded p-1.5 shadow-sm border">
      <div className="flex justify-between items-center mb-1">
        <h3 className="font-bold text-[11px] text-gray-800">오메가3 영양제 등록</h3>
        <button onClick={onReset} className="text-[9px] px-1 py-0 bg-gray-200 rounded hover:bg-gray-300">리셋</button>
      </div>
      <div className="space-y-0.5">
        {fields.map(({ key, label, unit }) => (
          <div key={key} className="flex items-center gap-0.5">
            <label className="text-[10px] w-16 shrink-0">{label}</label>
            <input type="number"
              className="w-16 text-[10px] border border-gray-300 rounded px-0.5 py-0 h-5 text-right"
              value={values[key] || ''} min={0} step="any"
              onChange={(e) => onUpdate({ [key]: e.target.value === '' ? '' : Number(e.target.value) })}
            />
            <span className="text-[9px] text-gray-400">{unit}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

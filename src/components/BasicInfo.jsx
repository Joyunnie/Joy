import { CALORIE_LABELS } from '../engine/calories';

export default function BasicInfo({ basicInfo, dailyCalories, onUpdate, onReset }) {
  return (
    <div className="bg-white rounded p-1.5 shadow-sm border">
      <div className="flex items-center justify-between mb-1">
        <h3 className="font-bold text-[11px] text-gray-800">기본 정보</h3>
        {onReset && (
          <button onClick={onReset}
            className="text-[10px] px-2 py-0.5 bg-gray-500 text-white rounded hover:bg-gray-600 font-semibold">레시피 초기화</button>
        )}
      </div>
      <div className="space-y-1">
        <div className="flex items-center gap-1">
          <label className="text-[10px] w-20 shrink-0">체중 (kg)</label>
          <input
            type="number"
            className="w-16 text-[10px] border border-gray-300 rounded px-0.5 py-0 h-5 text-right"
            value={basicInfo.weight}
            onChange={(e) => onUpdate({ weight: Number(e.target.value) || 0 })}
            min={0} step={0.1}
          />
        </div>
        <div>
          <label className="text-[10px] block mb-0.5">칼로리 타입</label>
          {CALORIE_LABELS.map(({ value, label }) => (
            <label key={value} className="flex items-center gap-0.5 text-[10px] cursor-pointer leading-tight">
              <input type="radio" name="calorieType" className="w-2.5 h-2.5"
                checked={basicInfo.calorieType === value}
                onChange={() => onUpdate({ calorieType: value })}
              />
              <span>{label}</span>
            </label>
          ))}
        </div>
        {(basicInfo.calorieType === 5 || basicInfo.calorieType === 6) && (
          <div className="flex items-center gap-1">
            <label className="text-[10px] w-20 shrink-0">예상체중 (kg)</label>
            <input type="number"
              className="w-16 text-[10px] border border-gray-300 rounded px-0.5 py-0 h-5 text-right"
              value={basicInfo.expectedWeight}
              onChange={(e) => onUpdate({ expectedWeight: Number(e.target.value) || 0 })}
              min={0} step={0.1}
            />
          </div>
        )}
        <div className="flex items-center gap-1">
          <label className="text-[10px] w-20 shrink-0">레시피 일수</label>
          <input type="number"
            className="w-16 text-[10px] border border-gray-300 rounded px-0.5 py-0 h-5 text-right"
            value={basicInfo.recipeDays}
            onChange={(e) => onUpdate({ recipeDays: Number(e.target.value) || 0 })}
            min={1}
          />
        </div>
        <div className="flex items-center gap-1 bg-blue-50 px-1 py-0.5 rounded">
          <label className="text-[10px] w-20 shrink-0 font-semibold">필요칼로리</label>
          {basicInfo.useCustomCalories ? (
            <input type="number"
              className="w-16 text-[10px] border border-blue-400 rounded px-0.5 py-0 h-5 text-right font-bold text-blue-700 bg-white"
              value={basicInfo.customCalories}
              onChange={(e) => onUpdate({ customCalories: e.target.value === '' ? '' : Number(e.target.value) })}
              min={0} step={0.1}
              placeholder="Kcal"
            />
          ) : (
            <span className="text-[10px] font-bold text-blue-700">{dailyCalories.toFixed(1)}</span>
          )}
          <span className="text-[10px] text-blue-700">Kcal</span>
          <label className="flex items-center gap-0.5 ml-auto cursor-pointer">
            <input type="checkbox" className="w-2.5 h-2.5"
              checked={!!basicInfo.useCustomCalories}
              onChange={(e) => onUpdate({ useCustomCalories: e.target.checked })}
            />
            <span className="text-[9px] text-gray-500">직접 입력</span>
          </label>
        </div>
      </div>
    </div>
  );
}

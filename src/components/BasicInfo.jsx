import { CALORIE_LABELS } from '../engine/calories';

export default function BasicInfo({ basicInfo, dailyCalories, onUpdate }) {
  return (
    <div className="bg-white rounded-lg p-3 shadow-sm border">
      <h3 className="font-bold text-sm mb-2 text-gray-800">기본 정보</h3>
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <label className="text-xs w-24 shrink-0">고양이 체중 (kg)</label>
          <input
            type="number"
            className="w-20 text-xs border border-gray-300 rounded px-1 py-0.5 text-right"
            value={basicInfo.weight}
            onChange={(e) => onUpdate({ weight: Number(e.target.value) || 0 })}
            min={0}
            step={0.1}
          />
        </div>

        <div>
          <label className="text-xs block mb-1">칼로리 타입</label>
          <div className="space-y-0.5">
            {CALORIE_LABELS.map(({ value, label }) => (
              <label key={value} className="flex items-center gap-1 text-xs cursor-pointer">
                <input
                  type="radio"
                  name="calorieType"
                  className="w-3 h-3"
                  checked={basicInfo.calorieType === value}
                  onChange={() => onUpdate({ calorieType: value })}
                />
                <span>{label}</span>
              </label>
            ))}
          </div>
        </div>

        {(basicInfo.calorieType === 5 || basicInfo.calorieType === 6) && (
          <div className="flex items-center gap-2">
            <label className="text-xs w-24 shrink-0">성묘 예상체중 (kg)</label>
            <input
              type="number"
              className="w-20 text-xs border border-gray-300 rounded px-1 py-0.5 text-right"
              value={basicInfo.expectedWeight}
              onChange={(e) => onUpdate({ expectedWeight: Number(e.target.value) || 0 })}
              min={0}
              step={0.1}
            />
          </div>
        )}

        <div className="flex items-center gap-2">
          <label className="text-xs w-24 shrink-0">레시피 일 수</label>
          <input
            type="number"
            className="w-20 text-xs border border-gray-300 rounded px-1 py-0.5 text-right"
            value={basicInfo.recipeDays}
            onChange={(e) => onUpdate({ recipeDays: Number(e.target.value) || 0 })}
            min={1}
          />
        </div>

        <div className="flex items-center gap-2 bg-blue-50 px-2 py-1 rounded">
          <label className="text-xs w-24 shrink-0 font-semibold">하루 필요칼로리</label>
          <span className="text-xs font-bold text-blue-700">{dailyCalories.toFixed(1)} Kcal</span>
        </div>
      </div>
    </div>
  );
}

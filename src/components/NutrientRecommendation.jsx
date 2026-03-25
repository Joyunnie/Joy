import { useState, useMemo } from 'react';
import { foods } from '../data/foodData';
import { NRC_MAPPING, getNrcValue, getNrcEntry } from '../engine/nutrients';

const fmt = (v) => v != null && !isNaN(v) ? v.toFixed(1) : '-';

export default function NutrientRecommendation({ sufficiency, daily, dailyCalories, isKitten, recipeDays, totals }) {
  const [open, setOpen] = useState(false);

  const deficientNutrients = useMemo(() => {
    if (!daily || !dailyCalories || dailyCalories <= 0) return [];

    const result = [];
    for (const [nutrientKey] of Object.entries(NRC_MAPPING)) {
      const suff = sufficiency[nutrientKey];
      if (suff == null || suff >= 1) continue;

      const nrcEntry = getNrcEntry(nutrientKey);
      const nrcVal = getNrcValue(nrcEntry, isKitten);
      if (nrcVal == null || nrcVal === 0) continue;

      const requirement = (nrcVal / 1000) * dailyCalories * recipeDays;
      const current = totals[nutrientKey] || 0;
      const deficit = requirement - current;
      if (deficit <= 0) continue;

      // Find top 3 foods with highest content for this nutrient
      const candidates = [];
      for (const food of foods) {
        const val = food.nutrients?.[nutrientKey];
        if (typeof val !== 'number' || val <= 0) continue;
        if (food.name === '물') continue;
        candidates.push({ name: food.name, per100: val });
      }
      candidates.sort((a, b) => b.per100 - a.per100);
      const top3 = candidates.slice(0, 3).map(c => ({
        name: c.name,
        per100: c.per100,
        needed: deficit / (c.per100 / 100),
      }));

      if (top3.length === 0) continue;

      result.push({
        key: nutrientKey,
        label: nutrientKey,
        suffPct: Math.round(suff * 100),
        deficit,
        recommendations: top3,
      });
    }

    result.sort((a, b) => a.suffPct - b.suffPct);
    return result;
  }, [sufficiency, daily, dailyCalories, isKitten, recipeDays, totals]);

  if (deficientNutrients.length === 0) return null;

  return (
    <div className="bg-white rounded p-1.5 shadow-sm border">
      <button onClick={() => setOpen(!open)} className="flex items-center gap-1 w-full text-left">
        <span className="text-[10px] font-bold text-gray-700">
          부족 영양소 추천 ({deficientNutrients.length}개)
        </span>
        <span className="text-[9px] text-gray-400 ml-auto">{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div className="mt-1 space-y-1.5 max-h-80 overflow-y-auto">
          {deficientNutrients.map(({ key, label, suffPct, deficit, recommendations }) => (
            <div key={key} className="border rounded p-1">
              <div className="flex items-center gap-1 mb-0.5">
                <span className={`text-[10px] font-semibold ${suffPct < 50 ? 'text-red-600' : 'text-orange-500'}`}>
                  {label}
                </span>
                <span className={`text-[9px] ${suffPct < 50 ? 'text-red-600' : 'text-orange-500'}`}>
                  ({suffPct}%)
                </span>
                <span className="text-[9px] text-gray-400 ml-auto">
                  부족량: {fmt(deficit)}
                </span>
              </div>
              <div className="space-y-0">
                {recommendations.map((rec, i) => (
                  <div key={i} className="flex items-center justify-between text-[9px] text-gray-600 pl-1">
                    <span className="truncate flex-1">{i + 1}. {rec.name}</span>
                    <span className="shrink-0 ml-1 text-blue-600 font-mono">{fmt(rec.needed)}g</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

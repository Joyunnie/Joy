import { useState, useMemo, useEffect, useCallback } from 'react';
import { foods } from '../data/foodData';
import { NRC_MAPPING, getNrcValue, getNrcEntry } from '../engine/nutrients';

const fmt = (v) => v != null && !isNaN(v) ? v.toFixed(1) : '-';
const BLACKLIST_KEY = 'catfood_recommend_blacklist';

function loadBlacklist() {
  try { return JSON.parse(localStorage.getItem(BLACKLIST_KEY)) || []; } catch { return []; }
}
function saveBlacklist(list) {
  localStorage.setItem(BLACKLIST_KEY, JSON.stringify(list));
}

const AMINO_ACID_KEYS = new Set([
  '이소루신(mg)', '루신(mg)', '라이신(mg)', '메티오닌(mg)', '시스테인(mg)',
  '페닐알라린(mg)', '티로신(mg)', '트레오닌(mg)', '트립토판(mg)', '발린(mg)',
  '히스티딘(mg)', '아르기닌(mg)', '알라닌(mg)', '아스파르트산(mg)',
  '글루탐산(mg)', '글리신(mg)', '프롤린(mg)', '세린(mg)',
]);

export default function NutrientRecommendation({ sufficiency, daily, dailyCalories, isKitten, recipeDays, totals }) {
  const [open, setOpen] = useState(false);
  const [blacklist, setBlacklist] = useState(loadBlacklist);
  const [showBlacklist, setShowBlacklist] = useState(false);

  useEffect(() => { saveBlacklist(blacklist); }, [blacklist]);

  const addToBlacklist = useCallback((name) => {
    setBlacklist(prev => prev.includes(name) ? prev : [...prev, name]);
  }, []);

  const removeFromBlacklist = useCallback((name) => {
    setBlacklist(prev => prev.filter(n => n !== name));
  }, []);

  const blacklistSet = useMemo(() => new Set(blacklist), [blacklist]);

  const deficientNutrients = useMemo(() => {
    if (!daily || !dailyCalories || dailyCalories <= 0) return [];

    const result = [];
    for (const [nutrientKey] of Object.entries(NRC_MAPPING)) {
      // 성묘(칼로리타입 1~4)일 때 아미노산 제외 (타우린 제외)
      if (!isKitten && AMINO_ACID_KEYS.has(nutrientKey)) continue;

      const suff = sufficiency[nutrientKey];
      if (suff == null || suff >= 1) continue;

      const nrcEntry = getNrcEntry(nutrientKey);
      const nrcVal = getNrcValue(nrcEntry, isKitten);
      if (nrcVal == null || nrcVal === 0) continue;

      const requirement = (nrcVal / 1000) * dailyCalories * recipeDays;
      const current = totals[nutrientKey] || 0;
      const deficit = requirement - current;
      if (deficit <= 0) continue;

      // Find top 3 foods (excluding blacklisted) with highest content
      const candidates = [];
      for (const food of foods) {
        const val = food.nutrients?.[nutrientKey];
        if (typeof val !== 'number' || val <= 0) continue;
        if (food.name === '물') continue;
        if (blacklistSet.has(food.name)) continue;
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
  }, [sufficiency, daily, dailyCalories, isKitten, recipeDays, totals, blacklistSet]);

  if (deficientNutrients.length === 0 && blacklist.length === 0) return null;

  return (
    <div className="bg-white rounded p-1.5 shadow-sm border">
      <button onClick={() => setOpen(!open)} className="flex items-center gap-1 w-full text-left">
        <span className="text-[10px] font-bold text-gray-700">
          부족 영양소 추천 ({deficientNutrients.length}개)
        </span>
        {blacklist.length > 0 && (
          <span className="text-[8px] text-gray-400">제외 {blacklist.length}</span>
        )}
        <span className="text-[9px] text-gray-400 ml-auto">{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div className="mt-1 space-y-1.5">
          {/* Blacklist management */}
          <div>
            <button
              onClick={() => setShowBlacklist(!showBlacklist)}
              className="text-[9px] text-gray-500 hover:text-gray-700"
            >
              제외된 재료 ({blacklist.length}) {showBlacklist ? '▲' : '▼'}
            </button>
            {showBlacklist && blacklist.length > 0 && (
              <div className="mt-0.5 border rounded p-1 bg-gray-50 max-h-24 overflow-y-auto">
                {blacklist.map(name => (
                  <div key={name} className="flex items-center justify-between text-[9px] py-0.5">
                    <span className="text-gray-500 line-through truncate">{name}</span>
                    <button
                      onClick={() => removeFromBlacklist(name)}
                      className="text-[9px] text-green-500 hover:text-green-700 shrink-0 ml-1 px-0.5"
                    >복원</button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Recommendations */}
          <div className="max-h-80 overflow-y-auto space-y-1.5">
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
                    <div key={i} className="flex items-center text-[9px] text-gray-600 pl-1">
                      <span className="truncate flex-1">{i + 1}. {rec.name}</span>
                      <span className="shrink-0 ml-1 text-blue-600 font-mono">{fmt(rec.needed)}g</span>
                      <button
                        onClick={() => addToBlacklist(rec.name)}
                        className="shrink-0 ml-0.5 text-[8px] text-red-400 hover:text-red-600 px-0.5"
                        title="추천 제외"
                      >✕</button>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

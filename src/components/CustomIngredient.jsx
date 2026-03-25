import { useState } from 'react';
import { NUTRIENT_KEYS } from '../engine/nutrients';
import { getCustomFoods, addCustomFood, removeCustomFood } from '../data/foodData';

const COMMON_KEYS = [
  '칼로리(Kcal)', '수분(g)', '단백질(g)', '지방(g)', '탄수화물(g)',
  '칼슘(mg)', '인(mg)', '나트륨(mg)', '철(mg)', '비타민A(mcg)',
  '비타민E(mg)', 'EPA(mg)', 'DHA(mg)', '타우린(mg)',
];

export default function CustomIngredient({ onUpdate }) {
  const [open, setOpen] = useState(false);
  const [showAll, setShowAll] = useState(false);
  const [name, setName] = useState('');
  const [unit, setUnit] = useState('100g');
  const [nutrients, setNutrients] = useState({});
  const [customFoods, setCustomFoods] = useState(getCustomFoods());

  const handleAdd = () => {
    if (!name.trim()) return;
    const food = {
      name: name.trim(),
      nutrients: { '함량(g)': unit, ...nutrients },
    };
    addCustomFood(food);
    setCustomFoods(getCustomFoods());
    setName('');
    setNutrients({});
    if (onUpdate) onUpdate();
  };

  const handleRemove = (idx) => {
    removeCustomFood(idx);
    setCustomFoods(getCustomFoods());
    if (onUpdate) onUpdate();
  };

  const displayKeys = showAll ? NUTRIENT_KEYS : COMMON_KEYS;

  return (
    <div className="bg-white rounded p-1.5 shadow-sm border">
      <button onClick={() => setOpen(!open)} className="flex items-center gap-1 w-full text-left">
        <span className="text-[10px] font-bold text-gray-700">커스텀 재료 등록</span>
        <span className="text-[9px] text-gray-400 ml-auto">{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div className="mt-1 space-y-1">
          <div className="flex gap-1">
            <input
              type="text"
              className="flex-1 text-[10px] border border-gray-300 rounded px-1 py-0.5"
              placeholder="재료명"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
            <select
              className="text-[10px] border border-gray-300 rounded px-0.5 py-0.5"
              value={unit}
              onChange={(e) => setUnit(e.target.value)}
            >
              <option value="100g">100g</option>
              <option value="100캡슐">100캡슐</option>
              <option value="100겔">100겔</option>
              <option value="100tsp">100tsp</option>
              <option value="100mg">100mg</option>
            </select>
          </div>
          <div className="max-h-40 overflow-y-auto border rounded p-1 space-y-0.5">
            {displayKeys.map((key) => (
              <div key={key} className="flex items-center gap-1">
                <label className="text-[9px] w-24 shrink-0 text-gray-600 truncate" title={key}>{key}</label>
                <input
                  type="number"
                  className="w-20 text-[10px] border border-gray-300 rounded px-0.5 py-0 text-right"
                  value={nutrients[key] || ''}
                  onChange={(e) => setNutrients(prev => ({
                    ...prev,
                    [key]: e.target.value === '' ? undefined : Number(e.target.value)
                  }))}
                  step="any"
                  placeholder="0"
                />
              </div>
            ))}
          </div>
          <div className="flex gap-1">
            <button
              onClick={() => setShowAll(!showAll)}
              className="text-[9px] text-blue-600 hover:underline"
            >
              {showAll ? '주요 영양소만' : `전체 ${NUTRIENT_KEYS.length}개 보기`}
            </button>
            <button
              onClick={handleAdd}
              className="ml-auto text-[10px] px-1.5 py-0.5 bg-green-600 text-white rounded hover:bg-green-700"
            >
              등록
            </button>
          </div>

          {customFoods.length > 0 && (
            <div className="border-t pt-1 mt-1">
              <div className="text-[9px] font-semibold text-gray-500 mb-0.5">등록된 재료</div>
              {customFoods.map((cf, i) => (
                <div key={i} className="flex items-center gap-1 text-[10px]">
                  <span className="flex-1 truncate">{cf.name}</span>
                  <button
                    onClick={() => handleRemove(i)}
                    className="text-[9px] text-red-400 hover:text-red-600 px-0.5"
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

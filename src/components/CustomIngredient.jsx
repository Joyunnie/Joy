import { useState } from 'react';
import { NUTRIENT_KEYS } from '../engine/nutrients';
import { getCustomFoods, addCustomFood, removeCustomFood, updateCustomFood } from '../data/foodData';

const COMMON_KEYS = [
  '칼로리(Kcal)', '수분(g)', '단백질(g)', '지방(g)', '탄수화물(g)',
  '칼슘(mg)', '인(mg)', '나트륨(mg)', '철(mg)', '비타민A(mcg)',
  '비타민E(mg)', 'EPA(mg)', 'DHA(mg)', '타우린(mg)',
];

// Mapping from food DB nutrient names to app nutrient keys
const NUTRIENT_NAME_MAP = {
  '에너지(kcal)': '칼로리(Kcal)',
  '수분(g)': '수분(g)',
  '단백질(g)': '단백질(g)',
  '지방(g)': '지방(g)',
  '탄수화물(g)': '탄수화물(g)',
  '총 식이섬유(g)': null,
  '칼슘(mg)': '칼슘(mg)',
  '철(mg)': '철(mg)',
  '인(mg)': '인(mg)',
  '칼륨(mg)': '칼륨(mg)',
  '나트륨(mg)': '나트륨(mg)',
  '비타민 A(μg RAE)': '비타민A(mcg)',
  '레티놀(μg)': null,
  '베타카로틴(μg)': null,
  '티아민(mg)': '비타민B1(mg)',
  '리보플라빈(mg)': '비타민B2(mg)',
  '니아신(mg)': '나이아신(mg)',
  '비타민 C(mg)': null,
  '비타민 D(μg)': '비타민D(mcg)',
  '콜레스테롤(mg)': '콜레스테롤(mg)',
  '총 포화 지방산(g)': { key: '포화지방산(mg)', multiply: 1000 },
  '총 불포화 지방산(g)': { key: '불포화지방산(mg)', multiply: 1000 },
  '마그네슘(mg)': '마그네슘(mg)',
  '아연(mg)': '아연(mg)',
  '구리(μg)': { key: '구리(mg)', multiply: 0.001 },
  '망간(mg)': '망간(mg)',
  '셀레늄(μg)': '셀레늄(mcg)',
  '몰리브덴(μg)': null,
  '요오드(μg)': '요오드(mcg)',
  '비타민 B6(mg)': '비타민B6(mg)',
  '비타민 B12(μg)': '비타민B12(mcg)',
  '엽산(μg DFE)': '폴산(mcg)',
  '판토텐산(mg)': '판토텐산(mg)',
  '비타민 E(mg α-TE)': '비타민E(mg)',
  '비타민 K(μg)': '비타민K(mcg)',
  '이소류신(mg)': '이소루신(mg)',
  '류신(mg)': '루신(mg)',
  '라이신(mg)': '라이신(mg)',
  '메티오닌(mg)': '메티오닌(mg)',
  '시스테인(mg)': '시스테인(mg)',
  '페닐알라닌(mg)': '페닐알라린(mg)',
  '티로신(mg)': '티로신(mg)',
  '트레오닌(mg)': '트레오닌(mg)',
  '트립토판(mg)': '트립토판(mg)',
  '발린(mg)': '발린(mg)',
  '히스티딘(mg)': '히스티딘(mg)',
  '아르기닌(mg)': '아르기닌(mg)',
  '알라닌(mg)': '알라닌(mg)',
  '아스파르트산(mg)': '아스파르트산(mg)',
  '글루탐산(mg)': '글루탐산(mg)',
  '글리신(mg)': '글리신(mg)',
  '프롤린(mg)': '프롤린(mg)',
  '세린(mg)': '세린(mg)',
  '타우린(mg)': '타우린(mg)',
  '총 지방산(g)': { key: '총지방산(mg)', multiply: 1000 },
  'n-3 지방산(g)': { key: 'n-3(mg)', multiply: 1000 },
  'n-6 지방산(g)': { key: 'n-6(mg)', multiply: 1000 },
  '리놀레산(g)': { key: '리놀레산(mg)', multiply: 1000 },
  '알파 리놀렌산(g)': { key: '알파리놀렌산(mg)', multiply: 1000 },
  'EPA(mg)': 'EPA(mg)',
  'DHA(mg)': 'DHA(mg)',
};

function parseNutrientText(text) {
  const result = {};
  const lines = text.split('\n').filter(l => l.trim());
  for (const line of lines) {
    // Tab-separated or multi-space separated
    const parts = line.split(/\t+/).map(s => s.trim());
    if (parts.length < 2) continue;
    const dbName = parts[0];
    const rawVal = parts[parts.length - 1].replace(/,/g, '');
    const numVal = parseFloat(rawVal);
    if (isNaN(numVal)) continue;

    const mapping = NUTRIENT_NAME_MAP[dbName];
    if (mapping === null || mapping === undefined) continue;

    if (typeof mapping === 'string') {
      result[mapping] = numVal;
    } else if (typeof mapping === 'object' && mapping.key) {
      result[mapping.key] = numVal * mapping.multiply;
    }
  }
  return result;
}

export default function CustomIngredient({ onUpdate }) {
  const [open, setOpen] = useState(false);
  const [showAll, setShowAll] = useState(false);
  const [name, setName] = useState('');
  const [unit, setUnit] = useState('100g');
  const [nutrients, setNutrients] = useState({});
  const [customFoods, setCustomFoods] = useState(getCustomFoods());
  const [pasteText, setPasteText] = useState('');
  const [editIndex, setEditIndex] = useState(null); // null = add mode, number = editing

  const resetForm = () => {
    setName('');
    setUnit('100g');
    setNutrients({});
    setPasteText('');
    setEditIndex(null);
  };

  const handleAdd = () => {
    if (!name.trim()) return;
    const food = {
      name: name.trim(),
      nutrients: { '함량(g)': unit, ...nutrients },
    };
    if (editIndex !== null) {
      updateCustomFood(editIndex, food);
    } else {
      addCustomFood(food);
    }
    setCustomFoods(getCustomFoods());
    resetForm();
    if (onUpdate) onUpdate();
  };

  const handleRemove = (idx) => {
    removeCustomFood(idx);
    setCustomFoods(getCustomFoods());
    if (onUpdate) onUpdate();
  };

  const handleEdit = (idx) => {
    const cf = customFoods[idx];
    setName(cf.name);
    setUnit(cf.nutrients['함량(g)'] || '100g');
    const nut = { ...cf.nutrients };
    delete nut['함량(g)'];
    setNutrients(nut);
    setEditIndex(idx);
  };

  const handleParse = () => {
    if (!pasteText.trim()) return;
    const parsed = parseNutrientText(pasteText);
    setNutrients(prev => ({ ...prev, ...parsed }));
  };

  const displayKeys = showAll ? NUTRIENT_KEYS : COMMON_KEYS;

  return (
    <div className="bg-white rounded p-1.5 shadow-sm border">
      <button onClick={() => setOpen(!open)} className="flex items-center gap-1 w-full text-left">
        <span className="text-[10px] font-bold text-gray-700">커스텀 재료 관리</span>
        <span className="text-[9px] text-gray-400 ml-auto">{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div className="mt-1 space-y-1">
          {/* Paste-to-parse area */}
          <div>
            <div className="text-[9px] text-gray-500 mb-0.5">식품영양DB 텍스트 붙여넣기</div>
            <textarea
              className="w-full text-[9px] border border-gray-300 rounded px-1 py-0.5 h-16 resize-y font-mono"
              placeholder={"에너지(kcal)\t150\n단백질(g)\t20.5\n지방(g)\t8.3"}
              value={pasteText}
              onChange={(e) => setPasteText(e.target.value)}
            />
            <button
              onClick={handleParse}
              className="text-[9px] px-1.5 py-0.5 bg-blue-500 text-white rounded hover:bg-blue-600"
            >
              파싱
            </button>
          </div>

          {/* Name + Unit */}
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

          {/* Nutrient inputs */}
          <div className="max-h-40 overflow-y-auto border rounded p-1 space-y-0.5">
            {displayKeys.map((key) => (
              <div key={key} className="flex items-center gap-1">
                <label className="text-[9px] w-24 shrink-0 text-gray-600 truncate" title={key}>{key}</label>
                <input
                  type="number"
                  className="w-20 text-[10px] border border-gray-300 rounded px-0.5 py-0 text-right"
                  value={nutrients[key] != null ? nutrients[key] : ''}
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

          {/* Actions */}
          <div className="flex gap-1 items-center">
            <button
              onClick={() => setShowAll(!showAll)}
              className="text-[9px] text-blue-600 hover:underline"
            >
              {showAll ? '주요 영양소만' : `전체 ${NUTRIENT_KEYS.length}개 보기`}
            </button>
            {editIndex !== null && (
              <button
                onClick={resetForm}
                className="text-[9px] text-gray-500 hover:underline ml-1"
              >
                취소
              </button>
            )}
            <button
              onClick={handleAdd}
              className="ml-auto text-[10px] px-1.5 py-0.5 bg-green-600 text-white rounded hover:bg-green-700"
            >
              {editIndex !== null ? '수정' : '등록'}
            </button>
          </div>

          {/* Registered custom foods list */}
          {customFoods.length > 0 && (
            <div className="border-t pt-1 mt-1">
              <div className="text-[9px] font-semibold text-gray-500 mb-0.5">등록된 재료</div>
              {customFoods.map((cf, i) => (
                <div key={i} className="flex items-center gap-1 text-[10px]">
                  <span className="flex-1 truncate">{cf.name}</span>
                  <button
                    onClick={() => handleEdit(i)}
                    className="text-[9px] text-blue-400 hover:text-blue-600 px-0.5"
                  >
                    편집
                  </button>
                  <button
                    onClick={() => handleRemove(i)}
                    className="text-[9px] text-red-400 hover:text-red-600 px-0.5"
                  >
                    삭제
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

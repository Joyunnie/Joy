import { useState } from 'react';
import { NUTRIENT_KEYS } from '../engine/nutrients';
import {
  ALL_CATEGORY_KEYS, CATEGORY_LABELS,
  getManagedItems, getDeletedItems,
  addFood, updateFood, deleteFood, restoreFood,
} from '../data/foodData';

const COMMON_KEYS = [
  '칼로리(Kcal)', '수분(g)', '단백질(g)', '지방(g)', '탄수화물(g)',
  '칼슘(mg)', '인(mg)', '나트륨(mg)', '철(mg)', '비타민A(mcg)',
  '비타민E(mg)', 'EPA(mg)', 'DHA(mg)', '타우린(mg)',
];

// --- Parsing (unchanged) ---

const NUTRIENT_NAME_MAP = {
  '에너지': '칼로리(Kcal)',
  '단백질': '단백질(g)',
  '지방': '지방(g)',
  '탄수화물': '탄수화물(g)',
  '수분': '수분(g)',
  '나트륨': '나트륨(mg)',
  '구리': '구리(mg)',
  '마그네슘': '마그네슘(mg)',
  '망간': '망간(mg)',
  '셀레늄': '셀레늄(mcg)',
  '아연': '아연(mg)',
  '요오드': '요오드(mcg)',
  '인': '인(mg)',
  '철': '철(mg)',
  '칼륨': '칼륨(mg)',
  '칼슘': '칼슘(mg)',
  '콜레스테롤': '콜레스테롤(mg)',
  '니아신': '나이아신(mg)',
  '비타민 B1/티아민': '비타민B1(mg)',
  '비타민 B2/리보플라빈': '비타민B2(mg)',
  '비타민 B12': '비타민B12(mcg)',
  '엽산': '폴산(mcg)',
  '판토텐산': '판토텐산(mg)',
  '비타민 A': '비타민A(mcg)',
  '비타민 D': '비타민D(mcg)',
  '비타민 E': '비타민E(mg)',
  '비타민 K1': '비타민K(mcg)',
  '피리독신': '비타민B6(mg)',
  '글루탐산': '글루탐산(mg)',
  '글리신': '글리신(mg)',
  '라이신': '라이신(mg)',
  '류신/루신': '루신(mg)',
  '메티오닌': '메티오닌(mg)',
  '발린': '발린(mg)',
  '세린': '세린(mg)',
  '시스테인': '시스테인(mg)',
  '아르기닌': '아르기닌(mg)',
  '아스파르트산': '아스파르트산(mg)',
  '알라닌': '알라닌(mg)',
  '이소류신/이소루신': '이소루신(mg)',
  '타우린': '타우린(mg)',
  '트레오닌': '트레오닌(mg)',
  '트립토판': '트립토판(mg)',
  '티로신': '티로신(mg)',
  '페닐알라닌': '페닐알라린(mg)',
  '프롤린': '프롤린(mg)',
  '히스티딘': '히스티딘(mg)',
  '포화지방산': '포화지방산(mg)',
  '불포화지방산': '불포화지방산(mg)',
  '리놀레산(18:2 n-6)': '리놀레산(mg)',
  '알파리놀렌산(18:3 n-3)': '알파리놀렌산(mg)',
  '에이코사펜타에노산(EPA, 20:5 n-3)': 'EPA(mg)',
  '도코사헥사에노산(DHA, 22:6 n-3)': 'DHA(mg)',
  '오메가 3 지방산': 'n-3(mg)',
  '오메가 6 지방산': 'n-6(mg)',
};

const UNIT_TO_GRAMS = { 'g': 1, 'mg': 0.001, 'mcg': 0.000001 };

function detectUnit(valueStr) {
  if (valueStr.includes('㎉') || valueStr.toLowerCase().includes('kcal')) return 'Kcal';
  if (valueStr.includes('㎍') || valueStr.includes('μg') || valueStr.toLowerCase().includes('mcg')) return 'mcg';
  if (valueStr.includes('㎎') || valueStr.toLowerCase().includes('mg')) return 'mg';
  if (/[0-9]g\b/i.test(valueStr) || valueStr.endsWith('g')) return 'g';
  return null;
}

function getTargetUnit(nutrientKey) {
  const match = nutrientKey.match(/\(([^)]+)\)/);
  return match ? match[1] : null;
}

function convertUnit(value, inputUnit, targetUnit) {
  if (inputUnit === targetUnit) return value;
  if (inputUnit === 'Kcal' || targetUnit === 'Kcal') return value;
  const inG = UNIT_TO_GRAMS[inputUnit];
  const outG = UNIT_TO_GRAMS[targetUnit];
  if (inG == null || outG == null) return value;
  return (value * inG) / outG;
}

function findMapping(name) {
  if (NUTRIENT_NAME_MAP[name]) return NUTRIENT_NAME_MAP[name];
  for (const [mapKey, targetKey] of Object.entries(NUTRIENT_NAME_MAP)) {
    if (name.includes(mapKey) || mapKey.includes(name)) return targetKey;
  }
  return null;
}

function parseNutritionText(text) {
  const result = {};
  const lines = text.split('\n');
  for (const line of lines) {
    let parts = line.split('\t');
    while (parts.length > 0 && parts[0].trim() === '') parts.shift();
    if (parts.length < 2) continue;
    const name = parts[0].trim();
    if (!name) continue;
    const valueStr = parts[1].trim();
    const numMatch = valueStr.replace(/,/g, '').match(/([0-9]+\.?[0-9]*)/);
    if (!numMatch) continue;
    let value = parseFloat(numMatch[1]);
    const inputUnit = detectUnit(valueStr);
    if (name === '지방산') {
      const targetUnit = getTargetUnit('총지방산(mg)');
      if (inputUnit && targetUnit) value = convertUnit(value, inputUnit, targetUnit);
      result['총지방산(mg)'] = value;
      continue;
    }
    const targetKey = findMapping(name);
    if (!targetKey) continue;
    const targetUnit = getTargetUnit(targetKey);
    if (inputUnit && targetUnit) value = convertUnit(value, inputUnit, targetUnit);
    result[targetKey] = value;
  }
  return result;
}

// --- Component ---

export default function CustomIngredient({ onUpdate }) {
  const [open, setOpen] = useState(false);
  const [selectedCat, setSelectedCat] = useState('식품R');
  const [showAll, setShowAll] = useState(true);
  const [name, setName] = useState('');
  const [unit, setUnit] = useState('100g');
  const [nutrients, setNutrients] = useState({});
  const [pasteText, setPasteText] = useState('');
  const [parsePreview, setParsePreview] = useState(null);
  const [editTarget, setEditTarget] = useState(null); // { type, index, catKey }
  const [refreshKey, setRefreshKey] = useState(0);

  const managedItems = getManagedItems(selectedCat);
  const deletedItems = getDeletedItems(selectedCat);

  const refresh = () => {
    setRefreshKey(k => k + 1);
    if (onUpdate) onUpdate();
  };

  const resetForm = () => {
    setName('');
    setUnit('100g');
    setNutrients({});
    setPasteText('');
    setParsePreview(null);
    setEditTarget(null);
  };

  const handleSave = () => {
    if (!name.trim()) return;
    const food = { name: name.trim(), nutrients: { '함량(g)': unit, ...nutrients } };
    if (editTarget) {
      updateFood(editTarget.catKey, editTarget.type, editTarget.index, food);
    } else {
      addFood(selectedCat, food);
    }
    resetForm();
    refresh();
  };

  const handleRemove = (item) => {
    deleteFood(item.catKey, item.type, item.index);
    refresh();
  };

  const handleRestore = (item) => {
    restoreFood(item.catKey, item.index);
    refresh();
  };

  const handleEdit = (item) => {
    setName(item.name);
    setUnit(item.nutrients?.['함량(g)'] || '100g');
    const nut = { ...item.nutrients };
    delete nut['함량(g)'];
    setNutrients(nut);
    setEditTarget({ type: item.type, index: item.index, catKey: item.catKey });
    setParsePreview(null);
    setPasteText('');
  };

  const handleParse = () => {
    if (!pasteText.trim()) return;
    setParsePreview(parseNutritionText(pasteText));
  };

  const handleApplyParse = () => {
    if (!parsePreview) return;
    setNutrients(prev => ({ ...prev, ...parsePreview }));
    setParsePreview(null);
    setPasteText('');
  };

  const displayKeys = showAll ? NUTRIENT_KEYS : COMMON_KEYS;
  const fmtVal = (v) => typeof v === 'number' ? (Number.isInteger(v) ? String(v) : v.toFixed(4).replace(/0+$/, '').replace(/\.$/, '')) : String(v);

  return (
    <div className="bg-white rounded p-1.5 shadow-sm border">
      <button onClick={() => setOpen(!open)} className="flex items-center gap-1 w-full text-left">
        <span className="text-[10px] font-bold text-gray-700">커스텀 재료 관리</span>
        <span className="text-[9px] text-gray-400 ml-auto">{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div className="mt-1 space-y-1">
          {/* Category selector */}
          <select
            className="w-full text-[10px] border border-gray-300 rounded px-1 py-0.5"
            value={selectedCat}
            onChange={(e) => { setSelectedCat(e.target.value); resetForm(); }}
          >
            {ALL_CATEGORY_KEYS.map(k => (
              <option key={k} value={k}>{k} ({CATEGORY_LABELS[k]})</option>
            ))}
          </select>

          {/* Items list for selected category */}
          <div className="border rounded max-h-32 overflow-y-auto">
            {managedItems.length === 0 && (
              <div className="text-[9px] text-gray-400 p-1">항목 없음</div>
            )}
            {managedItems.map((item) => (
              <div key={`${item.type}-${item.index}`} className="flex items-center gap-1 px-1 py-0.5 hover:bg-gray-50 border-b border-gray-100 last:border-0">
                <span className="flex-1 text-[10px] truncate">
                  {item.type === 'original' && <span className="text-[8px] text-gray-400 mr-0.5">[기본]</span>}
                  {item.name}
                </span>
                <button onClick={() => handleEdit(item)} className="text-[9px] text-blue-400 hover:text-blue-600 px-0.5 shrink-0">편집</button>
                <button onClick={() => handleRemove(item)} className="text-[9px] text-red-400 hover:text-red-600 px-0.5 shrink-0">삭제</button>
              </div>
            ))}
          </div>

          {/* Deleted originals - restore */}
          {deletedItems.length > 0 && (
            <div className="border rounded p-1">
              <div className="text-[9px] text-gray-400 mb-0.5">삭제된 기본 재료</div>
              {deletedItems.map((item) => (
                <div key={item.index} className="flex items-center gap-1 text-[10px] text-gray-400">
                  <span className="flex-1 truncate line-through">{item.name}</span>
                  <button onClick={() => handleRestore(item)} className="text-[9px] text-green-500 hover:text-green-700 px-0.5">복원</button>
                </div>
              ))}
            </div>
          )}

          {/* Separator */}
          <div className="border-t pt-1">
            <div className="text-[9px] font-semibold text-gray-500 mb-0.5">
              {editTarget ? `재료 수정 (${CATEGORY_LABELS[editTarget.catKey]})` : `새 재료 추가 → ${CATEGORY_LABELS[selectedCat]}`}
            </div>
          </div>

          {/* Paste-to-parse area */}
          <div>
            <div className="text-[9px] text-gray-500 mb-0.5">식품영양DB 텍스트 붙여넣기</div>
            <textarea
              className="w-full text-[9px] border border-gray-300 rounded px-1 py-0.5 h-16 resize-y font-mono"
              placeholder={"에너지\t135.00㎉\n단백질\t20.88g\n나트륨\t48.00㎎"}
              value={pasteText}
              onChange={(e) => { setPasteText(e.target.value); setParsePreview(null); }}
            />
            <button onClick={handleParse} className="text-[9px] px-1.5 py-0.5 bg-blue-500 text-white rounded hover:bg-blue-600">파싱</button>
          </div>

          {/* Parse preview */}
          {parsePreview && (
            <div className="border border-blue-200 bg-blue-50 rounded p-1">
              <div className="text-[9px] font-semibold text-blue-700 mb-0.5">파싱 결과 ({Object.keys(parsePreview).length}개 항목)</div>
              <div className="max-h-28 overflow-y-auto space-y-0">
                {Object.entries(parsePreview).map(([key, val]) => (
                  <div key={key} className="flex justify-between text-[9px]">
                    <span className="text-gray-600">{key}</span>
                    <span className="font-mono text-blue-800">{fmtVal(val)}</span>
                  </div>
                ))}
              </div>
              <button onClick={handleApplyParse} className="mt-0.5 text-[9px] px-1.5 py-0.5 bg-blue-600 text-white rounded hover:bg-blue-700">적용</button>
            </div>
          )}

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
                  className={`w-20 text-[10px] border rounded px-0.5 py-0 text-right ${nutrients[key] != null ? 'border-blue-400 bg-blue-50' : 'border-gray-300'}`}
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
            <button onClick={() => setShowAll(!showAll)} className="text-[9px] text-blue-600 hover:underline">
              {showAll ? '주요 영양소만' : `전체 ${NUTRIENT_KEYS.length}개 보기`}
            </button>
            {editTarget && (
              <button onClick={resetForm} className="text-[9px] text-gray-500 hover:underline ml-1">취소</button>
            )}
            <button onClick={handleSave} className="ml-auto text-[10px] px-1.5 py-0.5 bg-green-600 text-white rounded hover:bg-green-700">
              {editTarget ? '수정' : '등록'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

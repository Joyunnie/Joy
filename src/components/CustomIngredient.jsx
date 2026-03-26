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

// 가로형 탭 구분 열 순서 (자료시트 B~BG 열)
const HORIZONTAL_COLUMNS = [
  'name', 'unit',
  '칼로리(Kcal)', '수분(g)', '단백질(g)', '지방(g)', '탄수화물(g)',
  '비타민A(mcg)', '비타민D(mcg)', '비타민E(mg)', '비타민K(mcg)',
  '비타민B1(mg)', '비타민B2(mg)', '비타민B6(mg)', '나이아신(mg)',
  '판토텐산(mg)', '비타민B12(mcg)', '폴산(mcg)',
  '칼슘(mg)', '인(mg)', '마그네슘(mg)', '나트륨(mg)', '칼륨(mg)',
  '철(mg)', '구리(mg)', '아연(mg)', '망간(mg)', '셀레늄(mcg)', '요오드(mcg)',
  '이소루신(mg)', '루신(mg)', '라이신(mg)', '메티오닌(mg)', '시스테인(mg)',
  '페닐알라린(mg)', '티로신(mg)', '트레오닌(mg)', '트립토판(mg)', '발린(mg)',
  '히스티딘(mg)', '아르기닌(mg)', '알라닌(mg)', '아스파르트산(mg)',
  '글루탐산(mg)', '글리신(mg)', '프롤린(mg)', '세린(mg)', '타우린(mg)',
  '총지방산(mg)', '포화지방산(mg)', '불포화지방산(mg)', '콜레스테롤(mg)',
  'n-3(mg)', 'n-6(mg)', '리놀레산(mg)', '알파리놀렌산(mg)', 'EPA(mg)', 'DHA(mg)',
];

// --- USDA (English vertical) format ---

const USDA_NAME_MAP = {
  'Water': '수분(g)',
  'Energy': { key: '칼로리(Kcal)', unitFilter: 'kcal' },
  'Protein': '단백질(g)',
  'Total lipid (fat)': '지방(g)',
  'Carbohydrate, by difference': '탄수화물(g)',
  'Calcium, Ca': '칼슘(mg)',
  'Iron, Fe': '철(mg)',
  'Magnesium, Mg': '마그네슘(mg)',
  'Phosphorus, P': '인(mg)',
  'Potassium, K': '칼륨(mg)',
  'Sodium, Na': '나트륨(mg)',
  'Zinc, Zn': '아연(mg)',
  'Copper, Cu': '구리(mg)',
  'Manganese, Mn': '망간(mg)',
  'Selenium, Se': '셀레늄(mcg)',
  'Iodine, I': '요오드(mcg)',
  'Thiamin': '비타민B1(mg)',
  'Riboflavin': '비타민B2(mg)',
  'Niacin': '나이아신(mg)',
  'Pantothenic acid': '판토텐산(mg)',
  'Vitamin B-6': '비타민B6(mg)',
  'Folate, total': '폴산(mcg)',
  'Vitamin B-12': '비타민B12(mcg)',
  'Vitamin A, RAE': '비타민A(mcg)',
  'Vitamin E (alpha-tocopherol)': '비타민E(mg)',
  'Vitamin D (D2 + D3)': { key: '비타민D(mcg)', unitFilter: 'µg' },
  'Vitamin K (phylloquinone)': '비타민K(mcg)',
  'Vitamin C, total ascorbic acid': '비타민C(mg)',
  'Cholesterol': '콜레스테롤(mg)',
  'Fatty acids, total saturated': '포화지방산(mg)',
  'Fatty acids, total monounsaturated': '_mono(mg)',
  'Fatty acids, total polyunsaturated': '_poly(mg)',
  'Tryptophan': '트립토판(mg)',
  'Threonine': '트레오닌(mg)',
  'Isoleucine': '이소루신(mg)',
  'Leucine': '루신(mg)',
  'Lysine': '라이신(mg)',
  'Methionine': '메티오닌(mg)',
  'Cystine': '시스테인(mg)',
  'Phenylalanine': '페닐알라린(mg)',
  'Tyrosine': '티로신(mg)',
  'Valine': '발린(mg)',
  'Arginine': '아르기닌(mg)',
  'Histidine': '히스티딘(mg)',
  'Alanine': '알라닌(mg)',
  'Aspartic acid': '아스파르트산(mg)',
  'Glutamic acid': '글루탐산(mg)',
  'Glycine': '글리신(mg)',
  'Proline': '프롤린(mg)',
  'Serine': '세린(mg)',
  'PUFA 20:5 n-3 (EPA)': 'EPA(mg)',
  'PUFA 22:6 n-3 (DHA)': 'DHA(mg)',
  '20:5 n-3 (EPA)': 'EPA(mg)',
  '22:6 n-3 (DHA)': 'DHA(mg)',
  'PUFA 18:2 n-6 c,c': '리놀레산(mg)',
  '18:2 n-6 c,c': '리놀레산(mg)',
  'PUFA 18:3 n-3 c,c,c (ALA)': '알파리놀렌산(mg)',
  '18:3 n-3 c,c,c (ALA)': '알파리놀렌산(mg)',
  'PUFA 22:5 n-3 (DPA)': '_dpa(mg)',
  '22:5 n-3 (DPA)': '_dpa(mg)',
  'PUFA 20:4 n-6': '_ara(mg)',
  '20:4 n-6': '_ara(mg)',
};

// USDA 영문 키워드 감지용
const USDA_KEYWORDS = ['Energy', 'Protein', 'Water', 'Calcium, Ca', 'Iron, Fe', 'Thiamin', 'Riboflavin', 'Sodium, Na', 'Total lipid'];

function findUsdaMapping(name) {
  const entry = USDA_NAME_MAP[name];
  if (entry) return typeof entry === 'string' ? { key: entry } : entry;
  for (const [mapKey, val] of Object.entries(USDA_NAME_MAP)) {
    if (name.includes(mapKey) || mapKey.includes(name)) {
      return typeof val === 'string' ? { key: val } : val;
    }
  }
  return null;
}

// USDA 단위 문자열 → 내부 단위 정규화
function normalizeUsdaUnit(unitStr) {
  const u = unitStr.toLowerCase().trim();
  if (u === 'kcal' || u === '㎉') return 'Kcal';
  if (u === 'µg' || u === 'ug' || u === 'mcg' || u === '㎍') return 'mcg';
  if (u === 'mg' || u === '㎎') return 'mg';
  if (u === 'g') return 'g';
  if (u === 'iu') return 'IU';
  return null;
}

function parseUsdaText(text) {
  const result = {};
  const lines = text.split('\n');
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    if (/^\d{1,2}\/\d{1,2}\/\d{2,4}$/.test(trimmed)) continue;
    const parts = trimmed.split('\t');
    if (parts.length < 2) continue;
    const name = parts[0].trim();
    if (!name) continue;
    const valStr = parts[1].trim().replace(/,/g, '');
    const value = parseFloat(valStr);
    if (isNaN(value)) continue;
    const rawUnit = (parts[2] || '').trim();

    const mapping = findUsdaMapping(name);
    if (!mapping) continue;

    // unitFilter 체크 (Energy: kcal만, Vitamin D: µg만)
    if (mapping.unitFilter) {
      const filterLower = mapping.unitFilter.toLowerCase();
      const unitLower = rawUnit.toLowerCase();
      if (!unitLower.includes(filterLower) && !(filterLower === 'µg' && (unitLower === 'ug' || unitLower === 'mcg'))) continue;
    }

    // 자동 단위 감지 + 변환 (기존 convertUnit 재사용)
    const inputUnit = normalizeUsdaUnit(rawUnit);
    const targetUnit = getTargetUnit(mapping.key);
    let finalValue = value;
    if (inputUnit && targetUnit) {
      finalValue = convertUnit(value, inputUnit, targetUnit);
    }

    if (mapping.key && finalValue !== 0) {
      result[mapping.key] = (result[mapping.key] || 0) + finalValue;
    }
  }

  // 불포화지방산 합산: mono + poly
  const mono = result['_mono(mg)'] || 0;
  const poly = result['_poly(mg)'] || 0;
  if (mono + poly > 0) result['불포화지방산(mg)'] = mono + poly;
  delete result['_mono(mg)'];
  delete result['_poly(mg)'];

  // 총지방산 = 포화 + 불포화
  const sat = result['포화지방산(mg)'] || 0;
  const unsat = result['불포화지방산(mg)'] || 0;
  if (sat + unsat > 0) result['총지방산(mg)'] = sat + unsat;

  // n-3 합산: ALA + EPA + DHA + DPA
  const ala = result['알파리놀렌산(mg)'] || 0;
  const epa = result['EPA(mg)'] || 0;
  const dha = result['DHA(mg)'] || 0;
  const dpa = result['_dpa(mg)'] || 0;
  if (ala + epa + dha + dpa > 0) result['n-3(mg)'] = ala + epa + dha + dpa;
  delete result['_dpa(mg)'];

  // n-6 합산: 리놀레산 + 아라키돈산
  const linoleic = result['리놀레산(mg)'] || 0;
  const ara = result['_ara(mg)'] || 0;
  if (linoleic + ara > 0) result['n-6(mg)'] = linoleic + ara;
  delete result['_ara(mg)'];

  return result;
}

function isUsdaFormat(lines) {
  let matchCount = 0;
  const sample = lines.slice(0, 20);
  for (const line of sample) {
    const name = line.split('\t')[0]?.trim() || '';
    if (USDA_KEYWORDS.some(kw => name.includes(kw))) matchCount++;
  }
  return matchCount >= 2;
}

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

function parseVerticalText(text) {
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

function parseHorizontalLine(line) {
  const parts = line.split('\t').map(s => s.trim());
  if (parts.length < 3) return null;
  let colIdx = 0;
  let foodName = '';
  let nutrients = {};

  // 첫 번째 값이 숫자가 아니면 식품명
  if (isNaN(parseFloat(parts[0].replace(/,/g, '')))) {
    foodName = parts[0];
    colIdx = 1;
  }
  // 두 번째 값이 단위(100g 등)이면 건너뛰기
  if (colIdx < parts.length && /^\d+[a-zA-Z가-힣]+$/.test(parts[colIdx])) {
    colIdx++;
  }

  // 나머지 값을 HORIZONTAL_COLUMNS의 영양소 키에 순서대로 매핑
  const nutrientCols = HORIZONTAL_COLUMNS.filter(c => c !== 'name' && c !== 'unit');
  let nutIdx = 0;
  while (colIdx < parts.length && nutIdx < nutrientCols.length) {
    const raw = parts[colIdx].replace(/,/g, '');
    const num = raw === '' ? 0 : parseFloat(raw);
    if (!isNaN(num) && num !== 0) {
      nutrients[nutrientCols[nutIdx]] = num;
    }
    colIdx++;
    nutIdx++;
  }

  return { name: foodName, nutrients };
}

function detectFormatAndParse(text) {
  const lines = text.split('\n').filter(l => l.trim());
  if (lines.length === 0) return { type: 'empty', results: [] };

  // 1) 가로형 감지: 1~3줄이고 탭 구분 숫자가 10개 이상
  if (lines.length <= 3) {
    const tabs = lines[0].split('\t');
    const numCount = tabs.filter(t => !isNaN(parseFloat(t.trim().replace(/,/g, '')))).length;
    if (numCount >= 10) {
      const results = lines.map(l => parseHorizontalLine(l)).filter(Boolean);
      return { type: 'horizontal', results };
    }
  }

  // 여러 줄 가로형
  if (lines.length > 3) {
    const tabs = lines[0].split('\t');
    const numCount = tabs.filter(t => !isNaN(parseFloat(t.trim().replace(/,/g, '')))).length;
    if (numCount >= 10) {
      const results = lines.map(l => parseHorizontalLine(l)).filter(Boolean);
      return { type: 'horizontal', results };
    }
  }

  // 2) USDA 영문 형식 감지
  if (isUsdaFormat(lines)) {
    return { type: 'usda', results: [{ name: '', nutrients: parseUsdaText(text) }] };
  }

  // 3) 세로형 (기존 식약처 DB 형식)
  return { type: 'vertical', results: [{ name: '', nutrients: parseVerticalText(text) }] };
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
  const [horizontalResults, setHorizontalResults] = useState(null); // [{name, nutrients}, ...]
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
    setHorizontalResults(null);
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
    const { type, results } = detectFormatAndParse(pasteText);
    if (type === 'horizontal' && results.length > 0) {
      if (results.length === 1) {
        // 단일 가로형: 바로 미리보기
        if (results[0].name) setName(results[0].name);
        setParsePreview(results[0].nutrients);
        setHorizontalResults(null);
      } else {
        // 복수 가로형: 선택 목록 표시
        setHorizontalResults(results);
        setParsePreview(null);
      }
    } else if ((type === 'vertical' || type === 'usda') && results.length > 0) {
      setParsePreview(results[0].nutrients);
      setHorizontalResults(null);
    }
  };

  const handleSelectHorizontal = (item) => {
    if (item.name) setName(item.name);
    setNutrients(prev => ({ ...prev, ...item.nutrients }));
    setHorizontalResults(null);
    setPasteText('');
  };

  const handleRegisterAllHorizontal = () => {
    if (!horizontalResults) return;
    for (const item of horizontalResults) {
      const food = { name: item.name || '이름없음', nutrients: { '함량(g)': '100g', ...item.nutrients } };
      addFood(selectedCat, food);
    }
    setHorizontalResults(null);
    setPasteText('');
    refresh();
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
              <option key={k} value={k}>{CATEGORY_LABELS[k]}</option>
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
            <div className="text-[9px] text-gray-500 mb-0.5">영양 데이터 붙여넣기 (식약처/USDA/가로형 자동 감지)</div>
            <textarea
              className="w-full text-[9px] border border-gray-300 rounded px-1 py-0.5 h-16 resize-y font-mono"
              placeholder={"식약처: 에너지\\t135.00㎉\nUSDA: Protein\\t21.7\\tg\n가로형: 돼지등심\\t100g\\t142\\t..."}
              value={pasteText}
              onChange={(e) => { setPasteText(e.target.value); setParsePreview(null); setHorizontalResults(null); }}
            />
            <button onClick={handleParse} className="text-[9px] px-1.5 py-0.5 bg-blue-500 text-white rounded hover:bg-blue-600">파싱</button>
          </div>

          {/* 가로형 복수 결과 선택 목록 */}
          {horizontalResults && horizontalResults.length > 1 && (
            <div className="border border-green-200 bg-green-50 rounded p-1">
              <div className="text-[9px] font-semibold text-green-700 mb-0.5">
                가로형 파싱 결과 ({horizontalResults.length}개 식품)
              </div>
              <div className="max-h-36 overflow-y-auto space-y-0.5">
                {horizontalResults.map((item, i) => (
                  <div key={i} className="flex items-center gap-1 px-1 py-0.5 bg-white rounded border border-green-100">
                    <span className="flex-1 text-[10px] truncate">{item.name || `식품 ${i + 1}`}</span>
                    <span className="text-[8px] text-gray-400">{Object.keys(item.nutrients).length}개</span>
                    <button
                      onClick={() => handleSelectHorizontal(item)}
                      className="text-[9px] text-blue-500 hover:text-blue-700 px-0.5"
                    >선택</button>
                  </div>
                ))}
              </div>
              <button
                onClick={handleRegisterAllHorizontal}
                className="mt-0.5 text-[9px] px-1.5 py-0.5 bg-green-600 text-white rounded hover:bg-green-700"
              >전체 등록</button>
            </div>
          )}

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

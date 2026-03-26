import { useState, useEffect, useRef, useMemo } from 'react';
import { CELL_TO_SLOT, SLOT_DEFS } from '../data/appConfig';
import { getOverridesData, setOverridesData, getCategoryItems, getFoodByCategory } from '../data/foodData';
import { saveToGist } from './GistSync';
import { calcCalories } from '../engine/calories';

// 계산 데이터 시트 A열 행 → slotId 매핑
const CALC_SHEET_ROW_TO_SLOT = {
  4: 'calcium_0', 5: 'calcium_1', 6: 'calcium_2', 7: 'calcium_3', 8: 'calcium_4',
  10: 'meat_0', 11: 'meat_1', 12: 'meat_2', 13: 'meat_3', 14: 'meat_4',
  15: 'meat_5', 16: 'meat_6', 17: 'meat_7', 18: 'meat_8',
  20: 'organ_0', 21: 'organ_1', 22: 'organ_2', 23: 'organ_3', 24: 'organ_4',
  25: 'water_0',
  28: 'egg_0', 29: 'egg_1',
  31: 'vitB_0', 32: 'vitB_1',
  34: 'yeastTsp_0', 35: 'yeastG_0',
  37: 'vitE_0', 38: 'vitE_1',
  40: 'tauCap_0', 41: 'tauMg_0',
  43: 'omega_0', 44: 'omega_1',
  46: 'fiberTsp_0', 47: 'fiberTsp_1',
  48: 'fiberG_0', 49: 'fiberG_1',
  52: 'otherVeg_0', 55: 'otherVeg_1', 58: 'otherVeg_2',
  60: 'veggie_0', 64: 'veggie_1', 68: 'veggie_2',
  74: 'direct_0', 75: 'direct_1', 76: 'direct_2', 77: 'direct_3',
  78: 'direct_4', 79: 'direct_5', 80: 'direct_6',
};

// slotId → category key 빌드
const SLOT_TO_CATEGORY = {};
for (const def of SLOT_DEFS) {
  SLOT_TO_CATEGORY[def.id] = def.category;
}

function findDropdownIndexByName(categoryKey, foodName) {
  if (!foodName || !categoryKey) return 0;
  const items = getCategoryItems(categoryKey);
  // 정확한 매칭
  const exact = items.find(item => item.name === foodName);
  if (exact) return exact.index;
  // 부분 매칭 (괄호 등 미세 차이 대응)
  const partial = items.find(item =>
    item.name.includes(foodName) || foodName.includes(item.name)
  );
  if (partial) return partial.index;
  return 0;
}

const STORAGE_KEY = 'catfood_saved_recipes';
const OVERRIDES_KEY = 'catfood_overrides';
const TOKEN_KEY = 'catfood_gist_token';

function loadRecipes() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY)) || []; } catch { return []; }
}
function saveRecipes(recipes) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(recipes));
}

function autoSync() {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) saveToGist(token).catch(() => {});
}

function cellRef(col, row) { return `${col}${row}`; }

function parseExcelData(workbook) {
  const sheet = workbook.Sheets['레시피-결과'];
  if (!sheet) { alert("'레시피-결과' 시트를 찾을 수 없습니다."); return null; }
  const getVal = (cell) => { const c = sheet[cell]; return c?.v != null ? c.v : null; };
  const getNum = (cell) => { const v = getVal(cell); return typeof v === 'number' ? v : (v != null ? parseFloat(v) : null); };

  const weight = getNum('C4') || 4;
  const calorieType = getNum('B8') || 2;
  const expectedWeight = getNum('C11') || weight;
  const recipeDays = getNum('C13') || 60;
  const c12Calories = getNum('C12');
  const basicInfo = { weight, calorieType, expectedWeight, recipeDays };

  // C12 필요칼로리: 공식 계산값과 차이가 1 이상이면 직접 입력 모드
  if (c12Calories != null) {
    const formulaCal = calcCalories(calorieType, weight, expectedWeight);
    if (Math.abs(c12Calories - formulaCal) >= 1) {
      basicInfo.useCustomCalories = true;
      basicInfo.customCalories = c12Calories;
    }
  }

  const omega3Custom = {
    calories: getNum('C26') || '', fat: getNum('C27') || '', epa: getNum('C28') || '',
    dha: getNum('C29') || '', otherOmega3: getNum('C30') || '', vitE: getNum('C31') || '',
  };
  const nutrientAdjust = {
    protein: getNum('C34') || '', fat: getNum('C35') || '', calcium: getNum('C36') || '',
    phosphorus: getNum('C37') || '', sodium: getNum('C38') || '',
  };

  // 계산 데이터 시트에서 식품명 읽기 (이름 기반 매칭)
  const calcSheet = workbook.Sheets['계산 데이터 시트'];
  const getCalcVal = (cell) => { const c = calcSheet?.[cell]; return c?.v != null ? c.v : null; };

  const slotStates = {};
  const notFound = []; // 매칭 안 된 재료 목록

  // 1) 계산 데이터 시트 A열에서 식품명 → 이름 기반 드롭다운 매칭
  for (const [rowStr, slotId] of Object.entries(CALC_SHEET_ROW_TO_SLOT)) {
    const row = Number(rowStr);
    const foodName = getCalcVal(`A${row}`);
    if (!foodName || typeof foodName !== 'string' || !foodName.trim()) continue;
    const trimmedName = foodName.trim();
    if (slotId === 'water_0') continue; // 물은 별도 처리

    const categoryKey = SLOT_TO_CATEGORY[slotId];
    if (!categoryKey) continue;

    const dropdownIdx = findDropdownIndexByName(categoryKey, trimmedName);
    if (dropdownIdx > 0) {
      slotStates[slotId] = { ...slotStates[slotId], dropdown: dropdownIdx };
    } else {
      notFound.push(trimmedName);
    }
  }

  // 2) 레시피-결과 시트에서 값(amount) 읽기
  const valueCols = {
    'H': [4,5,6,7,8,10,11,12,13,14,15,16,17,18,20,21,22,23,24,25,28,29,30],
    'L': [4,5,7,8,10,11,13,14,16,17,19,20,22,23,24,25,28,29,30,36,37,38,39,40,41,42],
  };
  for (const [col, rows] of Object.entries(valueCols)) {
    for (const row of rows) {
      const cell = cellRef(col, row);
      const mapping = CELL_TO_SLOT[cell];
      if (!mapping || mapping.type !== 'value') continue;
      const val = getNum(cell);
      if (val != null && val > 0) slotStates[mapping.slotId] = { ...slotStates[mapping.slotId], amount: val };
    }
  }

  // 물 슬롯 처리
  if (slotStates.water_0?.amount) slotStates.water_0 = { ...slotStates.water_0, dropdown: 2 };

  // 매칭 안 된 재료 알림
  const uniqueNotFound = [...new Set(notFound)];
  if (uniqueNotFound.length > 0) {
    alert(`다음 재료를 찾을 수 없습니다. 커스텀 재료로 먼저 등록해주세요:\n${uniqueNotFound.join(', ')}`);
  }

  return { basicInfo, slotStates, omega3Custom, nutrientAdjust };
}

const CALORIE_TYPE_LABELS = {
  1: '비활동적 성묘', 2: '일반 성묘', 3: '활동적 성묘',
  4: '다이어트', 5: '자묘(~6개월)', 6: '자묘(7~12개월)',
};

// slotId → SLOT_DEFS entry lookup
const SLOT_DEF_MAP = {};
for (const def of SLOT_DEFS) SLOT_DEF_MAP[def.id] = def;

export default function RecipeManager({ basicInfo, slotStates, omega3Custom, nutrientAdjust, onLoadRecipe, resultRef, daily, totals, dailyCalories }) {
  const [recipes, setRecipes] = useState(loadRecipes);
  const [name, setName] = useState('');
  const [memo, setMemo] = useState('');
  const [open, setOpen] = useState(false);
  const fileInputRef = useRef(null);
  const excelInputRef = useRef(null);
  const cardRef = useRef(null);

  useEffect(() => { setRecipes(loadRecipes()); }, []);

  const sortedRecipes = useMemo(() =>
    [...recipes].sort((a, b) => (b.timestamp || 0) - (a.timestamp || 0)),
    [recipes]
  );

  // 레시피 카드용 재료 목록
  const activeIngredients = useMemo(() => {
    const items = [];
    for (const def of SLOT_DEFS) {
      const slot = slotStates[def.id];
      if (!slot?.amount || slot.amount <= 0) continue;
      const food = getFoodByCategory(def.category, slot.dropdown);
      const foodName = food?.name || def.label;
      items.push({ label: def.label, name: foodName, amount: slot.amount, unit: def.unit });
    }
    return items;
  }, [slotStates]);

  const handleSave = () => {
    const trimmed = name.trim();
    if (!trimmed) return;
    const recipe = {
      name: trimmed,
      date: new Date().toISOString().slice(0, 10),
      timestamp: Date.now(),
      memo: memo.trim(),
      basicInfo, slotStates, omega3Custom, nutrientAdjust,
    };
    const updated = [recipe, ...recipes.filter(r => r.name !== trimmed)];
    saveRecipes(updated);
    setRecipes(updated);
    setName(''); setMemo('');
    autoSync();
  };

  const handleDelete = (idx) => {
    const updated = recipes.filter((_, i) => i !== idx);
    saveRecipes(updated);
    setRecipes(updated);
    autoSync();
  };

  const handleOverwrite = (idx) => {
    const target = recipes[idx];
    if (!target) return;
    if (!confirm(`'${target.name}'에 현재 레시피를 덮어쓰시겠습니까?`)) return;
    const updated = [...recipes];
    updated[idx] = {
      ...target,
      date: new Date().toISOString().slice(0, 10),
      timestamp: Date.now(),
      memo: memo.trim() || target.memo || '',
      basicInfo, slotStates, omega3Custom, nutrientAdjust,
    };
    saveRecipes(updated);
    setRecipes(updated);
    autoSync();
  };

  const handleLoad = (recipe) => { onLoadRecipe(recipe); };

  const handleExport = () => {
    const data = {
      version: 1, exportDate: new Date().toISOString().slice(0, 10),
      recipes: loadRecipes(), overrides: getOverridesData(), omega3Custom,
    };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url;
    a.download = `catfood_backup_${data.exportDate}.json`; a.click();
    URL.revokeObjectURL(url);
  };

  const handleFileSelect = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      try { applyImport(JSON.parse(ev.target.result)); }
      catch { alert('올바른 JSON 파일이 아닙니다.'); }
      if (fileInputRef.current) fileInputRef.current.value = '';
    };
    reader.readAsText(file);
  };

  const mergeByName = (existing, incoming) => {
    const map = new Map(existing.map(item => [item.name, item]));
    for (const item of incoming) map.set(item.name, item);
    return [...map.values()];
  };

  const applyImport = (data) => {
    if (data.recipes) {
      const merged = mergeByName(loadRecipes(), data.recipes);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(merged));
    }
    if (data.overrides) {
      const existing = getOverridesData();
      const merged = { ...existing };
      for (const [catKey, catOv] of Object.entries(data.overrides)) {
        if (!merged[catKey]) { merged[catKey] = catOv; continue; }
        const m = merged[catKey];
        if (catOv.added) {
          if (!m.added) m.added = [];
          const existingNames = new Set(m.added.map(f => f.name));
          for (const f of catOv.added) {
            if (existingNames.has(f.name)) {
              const idx = m.added.findIndex(e => e.name === f.name);
              if (idx >= 0) m.added[idx] = f;
            } else m.added.push(f);
          }
        }
        if (catOv.modified) m.modified = { ...(m.modified || {}), ...catOv.modified };
        if (catOv.deleted) m.deleted = [...new Set([...(m.deleted || []), ...catOv.deleted])];
      }
      setOverridesData(merged);
    }
    window.location.reload();
  };

  const handleImageExport = async () => {
    if (!resultRef?.current) return;
    try {
      const { toPng } = await import('html-to-image');
      const dataUrl = await toPng(resultRef.current, { backgroundColor: '#ffffff' });
      const link = document.createElement('a');
      link.download = `recipe_${new Date().toISOString().slice(0, 10)}.png`;
      link.href = dataUrl; link.click();
    } catch (err) { alert(`이미지 저장 실패: ${err.message}`); }
  };

  const handleCardExport = async () => {
    if (!cardRef.current) return;
    try {
      const { toPng } = await import('html-to-image');
      const dataUrl = await toPng(cardRef.current, { backgroundColor: '#ffffff' });
      const link = document.createElement('a');
      link.download = `recipe_card_${new Date().toISOString().slice(0, 10)}.png`;
      link.href = dataUrl; link.click();
    } catch (err) { alert(`레시피 카드 저장 실패: ${err.message}`); }
  };

  const handleExcelSelect = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const XLSX = await import('xlsx');
      const data = await file.arrayBuffer();
      const workbook = XLSX.read(data, { type: 'array' });
      const parsed = parseExcelData(workbook);
      if (parsed) onLoadRecipe(parsed);
    } catch (err) { alert(`엑셀 파일 읽기 실패: ${err.message}`); }
    if (excelInputRef.current) excelInputRef.current.value = '';
  };

  return (
    <div className="bg-white rounded p-1.5 shadow-sm border">
      <button onClick={() => setOpen(!open)} className="flex items-center gap-1 w-full text-left">
        <span className="text-[10px] font-bold text-gray-700">레시피 저장/불러오기</span>
        <span className="text-[9px] text-gray-400 ml-auto">{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div className="mt-1 space-y-1">
          <div className="flex gap-1">
            <input type="text"
              className="flex-1 text-[10px] border border-gray-300 rounded px-1 py-0.5"
              placeholder="레시피 이름" value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSave()} />
            <button onClick={handleSave}
              className="text-[10px] px-1.5 py-0.5 bg-amber-500 text-white rounded hover:bg-amber-600 whitespace-nowrap">저장</button>
          </div>
          <textarea
            className="w-full text-[9px] border border-gray-300 rounded px-1 py-0.5 h-8 resize-y"
            placeholder="메모 (선택)" value={memo}
            onChange={(e) => setMemo(e.target.value)} />
          {sortedRecipes.length > 0 && (
            <div className="max-h-36 overflow-y-auto border rounded">
              {sortedRecipes.map((r) => {
                const origIdx = recipes.indexOf(r);
                return (
                  <div key={r.name + (r.timestamp || r.date)} className="px-1 py-0.5 hover:bg-gray-50 border-b border-gray-100 last:border-0">
                    <div className="flex items-center gap-1">
                      <button onClick={() => handleLoad(r)}
                        className="flex-1 text-left text-[10px] text-blue-700 hover:underline truncate">{r.name}</button>
                      <span className="text-[9px] text-gray-400 shrink-0">{r.date}</span>
                      <button onClick={() => handleOverwrite(origIdx)}
                        className="text-[9px] text-amber-500 hover:text-amber-700 shrink-0 px-0.5">덮어쓰기</button>
                      <button onClick={() => handleDelete(origIdx)}
                        className="text-[9px] text-red-400 hover:text-red-600 shrink-0 px-0.5">✕</button>
                    </div>
                    {r.memo && <div className="text-[9px] text-gray-400 truncate pl-1">{r.memo}</div>}
                  </div>
                );
              })}
            </div>
          )}

          <div className="flex gap-1 flex-wrap border-t pt-1">
            <button onClick={handleExport}
              className="text-[9px] px-1.5 py-0.5 bg-indigo-500 text-white rounded hover:bg-indigo-600">내보내기</button>
            <button onClick={() => fileInputRef.current?.click()}
              className="text-[9px] px-1.5 py-0.5 bg-teal-500 text-white rounded hover:bg-teal-600">가져오기</button>
            <button onClick={() => excelInputRef.current?.click()}
              className="text-[9px] px-1.5 py-0.5 bg-orange-500 text-white rounded hover:bg-orange-600">엑셀 가져오기</button>
            <button onClick={handleImageExport}
              className="text-[9px] px-1.5 py-0.5 bg-purple-500 text-white rounded hover:bg-purple-600">이미지로 저장</button>
            <button onClick={handleCardExport}
              className="text-[9px] px-1.5 py-0.5 bg-pink-500 text-white rounded hover:bg-pink-600">레시피 카드</button>
            <input ref={fileInputRef} type="file" accept=".json" className="hidden" onChange={handleFileSelect} />
            <input ref={excelInputRef} type="file" accept=".xlsx,.xlsm,.xls" className="hidden" onChange={handleExcelSelect} />
          </div>
        </div>
      )}

      {/* Hidden recipe card for image capture */}
      <div style={{ position: 'absolute', left: '-9999px', top: 0 }}>
        <div ref={cardRef} style={{ width: 480, padding: 20, fontFamily: 'sans-serif', background: '#fff' }}>
          <div style={{ borderBottom: '2px solid #d97706', paddingBottom: 8, marginBottom: 12 }}>
            <div style={{ fontSize: 16, fontWeight: 'bold', color: '#92400e' }}>고양이 생식 레시피</div>
            <div style={{ fontSize: 10, color: '#9ca3af', marginTop: 2 }}>
              {new Date().toISOString().slice(0, 10)} 생성
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 16px', fontSize: 11, marginBottom: 12 }}>
            <div><span style={{ color: '#6b7280' }}>체중:</span> {basicInfo.weight}kg</div>
            <div><span style={{ color: '#6b7280' }}>칼로리 타입:</span> {CALORIE_TYPE_LABELS[basicInfo.calorieType] || basicInfo.calorieType}</div>
            <div><span style={{ color: '#6b7280' }}>하루 필요 칼로리:</span> {dailyCalories?.toFixed(1) || '-'} Kcal</div>
            <div><span style={{ color: '#6b7280' }}>레시피 일수:</span> {basicInfo.recipeDays}일</div>
            <div><span style={{ color: '#6b7280' }}>총량:</span> {totals?._totalGrams?.toFixed(1) || '-'}g</div>
            <div><span style={{ color: '#6b7280' }}>하루 섭취량:</span> {daily?._dailyGrams?.toFixed(1) || '-'}g</div>
          </div>
          <div style={{ fontSize: 11, fontWeight: 'bold', color: '#374151', marginBottom: 4, borderBottom: '1px solid #e5e7eb', paddingBottom: 2 }}>
            재료 목록
          </div>
          <table style={{ width: '100%', fontSize: 10, borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: '#f9fafb', borderBottom: '1px solid #e5e7eb' }}>
                <th style={{ textAlign: 'left', padding: '2px 4px', color: '#6b7280' }}>재료</th>
                <th style={{ textAlign: 'right', padding: '2px 4px', color: '#6b7280' }}>사용량</th>
              </tr>
            </thead>
            <tbody>
              {activeIngredients.map((item, i) => (
                <tr key={i} style={{ borderBottom: '1px solid #f3f4f6' }}>
                  <td style={{ padding: '2px 4px' }}>{item.name}</td>
                  <td style={{ textAlign: 'right', padding: '2px 4px', fontFamily: 'monospace' }}>
                    {item.amount}{item.unit}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {activeIngredients.length === 0 && (
            <div style={{ fontSize: 10, color: '#9ca3af', textAlign: 'center', padding: 8 }}>재료 없음</div>
          )}
        </div>
      </div>
    </div>
  );
}

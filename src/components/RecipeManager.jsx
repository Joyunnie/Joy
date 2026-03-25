import { useState, useEffect, useRef } from 'react';
import { CELL_TO_SLOT } from '../data/appConfig';

const STORAGE_KEY = 'catfood_saved_recipes';
const R_FOODS_KEY = 'catfood_r_foods';
const CUSTOM_FOODS_KEY = 'catfood_custom_foods';

function loadRecipes() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY)) || [];
  } catch { return []; }
}

function saveRecipes(recipes) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(recipes));
}

// Excel cell ref helpers
function cellRef(col, row) {
  return `${col}${row}`;
}

function parseExcelData(workbook) {
  const sheet = workbook.Sheets['레시피-결과'];
  if (!sheet) {
    alert("'레시피-결과' 시트를 찾을 수 없습니다.");
    return null;
  }

  const getVal = (cell) => {
    const c = sheet[cell];
    if (!c) return null;
    return c.v != null ? c.v : null;
  };
  const getNum = (cell) => {
    const v = getVal(cell);
    return typeof v === 'number' ? v : (v != null ? parseFloat(v) : null);
  };

  // Basic info
  const weight = getNum('C4') || 4;
  const calorieType = getNum('B8') || 2;
  const expectedWeight = getNum('C11') || weight;
  const recipeDays = getNum('C13') || 60;

  const basicInfo = { weight, calorieType, expectedWeight, recipeDays };

  // Omega3 custom: C26~C31
  const omega3Custom = {
    calories: getNum('C26') || '',
    fat: getNum('C27') || '',
    epa: getNum('C28') || '',
    dha: getNum('C29') || '',
    otherOmega3: getNum('C30') || '',
    vitE: getNum('C31') || '',
  };

  // Nutrient adjust: C34~C38
  const nutrientAdjust = {
    protein: getNum('C34') || '',
    fat: getNum('C35') || '',
    calcium: getNum('C36') || '',
    phosphorus: getNum('C37') || '',
    sodium: getNum('C38') || '',
  };

  // Slot states from CELL_TO_SLOT mapping
  const slotStates = {};

  // Dropdown cells
  const dropdownCols = {
    'G': [4, 5, 6, 7, 8],
    'F': [10, 11, 12, 13, 14, 15, 16, 17, 18, 20, 21, 22, 23, 24, 25, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40],
    'K': [4, 5, 7, 8, 10, 11, 13, 14, 16, 17, 19, 20, 22, 23, 24, 25, 28, 29, 30, 31, 32, 33, 34, 36, 37, 38, 39, 40],
  };

  for (const [col, rows] of Object.entries(dropdownCols)) {
    for (const row of rows) {
      const cell = cellRef(col, row);
      const mapping = CELL_TO_SLOT[cell];
      if (!mapping || mapping.type !== 'dropdown') continue;
      const val = getNum(cell);
      if (val != null && val > 1) {
        slotStates[mapping.slotId] = { ...slotStates[mapping.slotId], dropdown: val };
      }
    }
  }

  // Value cells
  const valueCols = {
    'H': [4, 5, 6, 7, 8, 10, 11, 12, 13, 14, 15, 16, 17, 18, 20, 21, 22, 23, 24, 25, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40],
    'L': [4, 5, 7, 8, 10, 11, 13, 14, 16, 17, 19, 20, 22, 23, 24, 25, 28, 29, 30, 31, 32, 33, 34, 36, 37, 38, 39, 40],
  };

  for (const [col, rows] of Object.entries(valueCols)) {
    for (const row of rows) {
      const cell = cellRef(col, row);
      const mapping = CELL_TO_SLOT[cell];
      if (!mapping || mapping.type !== 'value') continue;
      const val = getNum(cell);
      if (val != null && val > 0) {
        slotStates[mapping.slotId] = { ...slotStates[mapping.slotId], amount: val };
      }
    }
  }

  // Water slot: set dropdown to 2 if it has amount
  if (slotStates.water_0?.amount) {
    slotStates.water_0 = { ...slotStates.water_0, dropdown: 2 };
  }

  return { basicInfo, slotStates, omega3Custom, nutrientAdjust };
}

export default function RecipeManager({ basicInfo, slotStates, omega3Custom, nutrientAdjust, onLoadRecipe }) {
  const [recipes, setRecipes] = useState(loadRecipes);
  const [name, setName] = useState('');
  const [open, setOpen] = useState(false);
  const fileInputRef = useRef(null);
  const excelInputRef = useRef(null);

  useEffect(() => { setRecipes(loadRecipes()); }, []);

  const handleSave = () => {
    const trimmed = name.trim();
    if (!trimmed) return;
    const recipe = {
      name: trimmed,
      date: new Date().toISOString().slice(0, 10),
      basicInfo,
      slotStates,
      omega3Custom,
      nutrientAdjust,
    };
    const updated = [recipe, ...recipes.filter(r => r.name !== trimmed)];
    saveRecipes(updated);
    setRecipes(updated);
    setName('');
  };

  const handleDelete = (idx) => {
    const updated = recipes.filter((_, i) => i !== idx);
    saveRecipes(updated);
    setRecipes(updated);
  };

  const handleLoad = (recipe) => {
    onLoadRecipe(recipe);
  };

  // --- Export ---
  const handleExport = () => {
    const data = {
      version: 1,
      exportDate: new Date().toISOString().slice(0, 10),
      recipes: loadRecipes(),
      customFoods: JSON.parse(localStorage.getItem(CUSTOM_FOODS_KEY) || '[]'),
      rFoodOverrides: JSON.parse(localStorage.getItem(R_FOODS_KEY) || '{}'),
      omega3Custom,
    };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `catfood_backup_${data.exportDate}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // --- JSON Import ---
  const handleFileSelect = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      try {
        const data = JSON.parse(ev.target.result);
        applyImport(data);
      } catch {
        alert('올바른 JSON 파일이 아닙니다.');
      }
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
    if (data.customFoods) {
      const existing = JSON.parse(localStorage.getItem(CUSTOM_FOODS_KEY) || '[]');
      const merged = mergeByName(existing, data.customFoods);
      localStorage.setItem(CUSTOM_FOODS_KEY, JSON.stringify(merged));
    }
    if (data.rFoodOverrides) {
      const existing = JSON.parse(localStorage.getItem(R_FOODS_KEY) || '{}');
      localStorage.setItem(R_FOODS_KEY, JSON.stringify({ ...existing, ...data.rFoodOverrides }));
    }
    window.location.reload();
  };

  // --- Excel Import ---
  const handleExcelSelect = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const XLSX = (await import('xlsx')).default;
      const data = await file.arrayBuffer();
      const workbook = XLSX.read(data);
      const parsed = parseExcelData(workbook);
      if (parsed) {
        onLoadRecipe(parsed);
      }
    } catch (err) {
      alert(`엑셀 파일 읽기 실패: ${err.message}`);
    }
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
            <input
              type="text"
              className="flex-1 text-[10px] border border-gray-300 rounded px-1 py-0.5"
              placeholder="레시피 이름"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSave()}
            />
            <button
              onClick={handleSave}
              className="text-[10px] px-1.5 py-0.5 bg-amber-500 text-white rounded hover:bg-amber-600 whitespace-nowrap"
            >
              저장
            </button>
          </div>
          {recipes.length > 0 && (
            <div className="max-h-28 overflow-y-auto border rounded">
              {recipes.map((r, i) => (
                <div key={i} className="flex items-center gap-1 px-1 py-0.5 hover:bg-gray-50 border-b border-gray-100 last:border-0">
                  <button
                    onClick={() => handleLoad(r)}
                    className="flex-1 text-left text-[10px] text-blue-700 hover:underline truncate"
                  >
                    {r.name}
                  </button>
                  <span className="text-[9px] text-gray-400 shrink-0">{r.date}</span>
                  <button
                    onClick={() => handleDelete(i)}
                    className="text-[9px] text-red-400 hover:text-red-600 shrink-0 px-0.5"
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Export / Import / Excel */}
          <div className="flex gap-1 flex-wrap border-t pt-1">
            <button
              onClick={handleExport}
              className="text-[9px] px-1.5 py-0.5 bg-indigo-500 text-white rounded hover:bg-indigo-600"
            >
              내보내기
            </button>
            <button
              onClick={() => fileInputRef.current?.click()}
              className="text-[9px] px-1.5 py-0.5 bg-teal-500 text-white rounded hover:bg-teal-600"
            >
              가져오기
            </button>
            <button
              onClick={() => excelInputRef.current?.click()}
              className="text-[9px] px-1.5 py-0.5 bg-orange-500 text-white rounded hover:bg-orange-600"
            >
              엑셀 가져오기
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept=".json"
              className="hidden"
              onChange={handleFileSelect}
            />
            <input
              ref={excelInputRef}
              type="file"
              accept=".xlsx,.xlsm,.xls"
              className="hidden"
              onChange={handleExcelSelect}
            />
          </div>
        </div>
      )}
    </div>
  );
}

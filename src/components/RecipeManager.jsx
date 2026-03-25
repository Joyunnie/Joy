import { useState, useEffect, useRef } from 'react';
import { CELL_TO_SLOT } from '../data/appConfig';
import { getOverridesData, setOverridesData } from '../data/foodData';
import { saveToGist } from './GistSync';

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
  const basicInfo = { weight, calorieType, expectedWeight, recipeDays };

  const omega3Custom = {
    calories: getNum('C26') || '', fat: getNum('C27') || '', epa: getNum('C28') || '',
    dha: getNum('C29') || '', otherOmega3: getNum('C30') || '', vitE: getNum('C31') || '',
  };
  const nutrientAdjust = {
    protein: getNum('C34') || '', fat: getNum('C35') || '', calcium: getNum('C36') || '',
    phosphorus: getNum('C37') || '', sodium: getNum('C38') || '',
  };

  const slotStates = {};
  const dropdownCols = {
    'G': [4,5,6,7,8],
    'F': [10,11,12,13,14,15,16,17,18,20,21,22,23,24,25,28,29,30],
    'K': [4,5,7,8,10,11,13,14,16,17,19,20,22,23,24,25,28,29,30,36,37,38,39,40,41,42],
  };
  for (const [col, rows] of Object.entries(dropdownCols)) {
    for (const row of rows) {
      const cell = cellRef(col, row);
      const mapping = CELL_TO_SLOT[cell];
      if (!mapping || mapping.type !== 'dropdown') continue;
      const val = getNum(cell);
      if (val != null && val > 1) slotStates[mapping.slotId] = { ...slotStates[mapping.slotId], dropdown: val };
    }
  }
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
  if (slotStates.water_0?.amount) slotStates.water_0 = { ...slotStates.water_0, dropdown: 2 };
  return { basicInfo, slotStates, omega3Custom, nutrientAdjust };
}

export default function RecipeManager({ basicInfo, slotStates, omega3Custom, nutrientAdjust, onLoadRecipe, resultRef }) {
  const [recipes, setRecipes] = useState(loadRecipes);
  const [name, setName] = useState('');
  const [memo, setMemo] = useState('');
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
      const html2canvas = (await import('html2canvas')).default;
      const canvas = await html2canvas(resultRef.current, { scale: 2, useCORS: true, backgroundColor: '#f3f4f6' });
      const link = document.createElement('a');
      link.download = `recipe_${new Date().toISOString().slice(0, 10)}.png`;
      link.href = canvas.toDataURL('image/png'); link.click();
    } catch (err) { alert(`이미지 저장 실패: ${err.message}`); }
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
          {recipes.length > 0 && (
            <div className="max-h-36 overflow-y-auto border rounded">
              {recipes.map((r, i) => (
                <div key={i} className="px-1 py-0.5 hover:bg-gray-50 border-b border-gray-100 last:border-0">
                  <div className="flex items-center gap-1">
                    <button onClick={() => handleLoad(r)}
                      className="flex-1 text-left text-[10px] text-blue-700 hover:underline truncate">{r.name}</button>
                    <span className="text-[9px] text-gray-400 shrink-0">{r.date}</span>
                    <button onClick={() => handleDelete(i)}
                      className="text-[9px] text-red-400 hover:text-red-600 shrink-0 px-0.5">✕</button>
                  </div>
                  {r.memo && <div className="text-[9px] text-gray-400 truncate pl-1">{r.memo}</div>}
                </div>
              ))}
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
            <input ref={fileInputRef} type="file" accept=".json" className="hidden" onChange={handleFileSelect} />
            <input ref={excelInputRef} type="file" accept=".xlsx,.xlsm,.xls" className="hidden" onChange={handleExcelSelect} />
          </div>
        </div>
      )}
    </div>
  );
}

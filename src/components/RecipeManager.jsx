import { useState, useEffect, useRef } from 'react';

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

export default function RecipeManager({ basicInfo, slotStates, omega3Custom, nutrientAdjust, onLoadRecipe }) {
  const [recipes, setRecipes] = useState(loadRecipes);
  const [name, setName] = useState('');
  const [open, setOpen] = useState(false);
  const fileInputRef = useRef(null);

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

  // --- Import ---
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

  // Merge helper: file items overwrite same-name existing, keep rest
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

          {/* Export / Import */}
          <div className="flex gap-1 border-t pt-1">
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
            <input
              ref={fileInputRef}
              type="file"
              accept=".json"
              className="hidden"
              onChange={handleFileSelect}
            />
          </div>
        </div>
      )}
    </div>
  );
}

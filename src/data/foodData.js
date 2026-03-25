import rawData from '../../food_data.json';

export const foods = rawData.foods;
export const categories = rawData.categories;

// Water is a special slot - always "물"
const waterFood = foods.find(f => f.name === '물' && f.id === '0');

// localStorage key for all category overrides
const OVERRIDES_KEY = 'catfood_overrides';

// Build original data maps (immutable reference)
const originalItems = {}; // catKey -> [...items]
const originalFoods = {}; // catKey -> { index -> { name, nutrients } }
for (const [catKey, catVal] of Object.entries(categories)) {
  originalItems[catKey] = [...catVal.items];
  originalFoods[catKey] = {};
  for (const item of catVal.items) {
    const food = foods.find(f => f.name === item.name);
    if (food) {
      originalFoods[catKey][item.index] = { name: food.name, nutrients: { ...food.nutrients } };
    }
  }
}

// Overrides structure per category:
// { added: [{ name, nutrients }], modified: { [index]: { name, nutrients } }, deleted: [index] }
let overrides = {};

// Effective lookup: catKey -> { index -> food }
const effectiveMap = {};

function loadOverrides() {
  try {
    overrides = JSON.parse(localStorage.getItem(OVERRIDES_KEY)) || {};
  } catch { overrides = {}; }
  rebuildAll();
}

function saveOverrides() {
  localStorage.setItem(OVERRIDES_KEY, JSON.stringify(overrides));
}

function getOverride(catKey) {
  if (!overrides[catKey]) overrides[catKey] = { added: [], modified: {}, deleted: [] };
  return overrides[catKey];
}

function rebuildAll() {
  for (const catKey of Object.keys(categories)) {
    rebuildCategory(catKey);
  }
}

function rebuildCategory(catKey) {
  effectiveMap[catKey] = {};
  const ov = overrides[catKey] || { added: [], modified: {}, deleted: [] };

  // Original items (with modifications/deletions)
  for (const item of (originalItems[catKey] || [])) {
    if (ov.deleted?.includes(item.index)) continue;
    if (ov.modified?.[item.index]) {
      effectiveMap[catKey][item.index] = ov.modified[item.index];
    } else if (originalFoods[catKey]?.[item.index]) {
      effectiveMap[catKey][item.index] = originalFoods[catKey][item.index];
    }
  }

  // Added items: index starts at 100
  if (ov.added) {
    ov.added.forEach((food, i) => {
      effectiveMap[catKey][100 + i] = food;
    });
  }
}

loadOverrides();

// --- Category labels for UI ---
export const CATEGORY_LABELS = {
  '식품A': '생뼈류',
  '식품AA': 'RMB',
  '식품B': '본밀류',
  '식품C': '달걀껍질',
  '식품D': '기타칼슘',
  '식품F': '고기류',
  '식품FF': '내장류',
  '식품G': '비타민B',
  '식품H': '효모(스푼)',
  '식품HH': '효모(g)',
  '식품I': '비타민E',
  '식품J': '타우린(캡슐)',
  '식품JJ': '타우린(mg)',
  '식품K': '오메가3',
  '식품L': '난류',
  '식품M': '식이섬유(tsp)',
  '식품MM': '식이섬유(g)',
  '식품P': '야채퓨레채소',
  '식품Q': '야채퓨레기타',
  '식품R': '직접넣는데이터',
};

export const ALL_CATEGORY_KEYS = Object.keys(CATEGORY_LABELS);

// --- Public API for UI ---

// Get all items for a category (original + added, excluding deleted)
export function getManagedItems(catKey) {
  const ov = overrides[catKey] || { added: [], modified: {}, deleted: [] };
  const result = [];

  // Original items
  for (const item of (originalItems[catKey] || [])) {
    if (ov.deleted?.includes(item.index)) continue;
    const food = ov.modified?.[item.index] || originalFoods[catKey]?.[item.index];
    if (food) {
      result.push({ type: 'original', index: item.index, catKey, name: food.name, nutrients: food.nutrients });
    }
  }

  // Added items
  if (ov.added) {
    ov.added.forEach((food, i) => {
      result.push({ type: 'added', index: i, catKey, name: food.name, nutrients: food.nutrients });
    });
  }

  return result;
}

// Get deleted original items for a category
export function getDeletedItems(catKey) {
  const ov = overrides[catKey] || { added: [], modified: {}, deleted: [] };
  const result = [];
  for (const idx of (ov.deleted || [])) {
    const orig = originalFoods[catKey]?.[idx];
    if (orig) result.push({ index: idx, catKey, name: orig.name });
  }
  return result;
}

// Add a new food to a category
export function addFood(catKey, food) {
  const ov = getOverride(catKey);
  ov.added.push(food);
  saveOverrides();
  rebuildCategory(catKey);
}

// Update an existing food
export function updateFood(catKey, type, index, food) {
  const ov = getOverride(catKey);
  if (type === 'original') {
    if (!ov.modified) ov.modified = {};
    ov.modified[index] = food;
  } else {
    // type === 'added'
    if (ov.added && ov.added[index]) {
      ov.added[index] = food;
    }
  }
  saveOverrides();
  rebuildCategory(catKey);
}

// Delete a food
export function deleteFood(catKey, type, index) {
  const ov = getOverride(catKey);
  if (type === 'original') {
    if (!ov.deleted) ov.deleted = [];
    if (!ov.deleted.includes(index)) ov.deleted.push(index);
    // Also remove any modification
    if (ov.modified) delete ov.modified[index];
  } else {
    // type === 'added'
    if (ov.added) ov.added = ov.added.filter((_, i) => i !== index);
  }
  saveOverrides();
  rebuildCategory(catKey);
}

// Restore a deleted original
export function restoreFood(catKey, index) {
  const ov = getOverride(catKey);
  if (ov.deleted) {
    ov.deleted = ov.deleted.filter(i => i !== index);
  }
  saveOverrides();
  rebuildCategory(catKey);
}

// --- Core lookup functions (used by calculation engine) ---

export function getFoodByCategory(categoryKey, dropdownIndex) {
  if (!dropdownIndex || dropdownIndex <= 1) return null;
  if (categoryKey === 'water') return waterFood;
  const catMap = effectiveMap[categoryKey];
  if (!catMap) return null;
  return catMap[dropdownIndex] || null;
}

export function getCategoryItems(categoryKey) {
  if (categoryKey === 'water') return [{ index: 2, name: '물' }];
  const catMap = effectiveMap[categoryKey];
  if (!catMap) {
    const cat = categories[categoryKey];
    return cat ? [...cat.items] : [];
  }
  return Object.entries(catMap).map(([idx, food]) => ({
    index: Number(idx),
    name: food.name,
  })).sort((a, b) => a.index - b.index);
}

// --- For export/import ---
export function getOverridesData() {
  return overrides;
}

export function setOverridesData(data) {
  overrides = data;
  saveOverrides();
  rebuildAll();
}

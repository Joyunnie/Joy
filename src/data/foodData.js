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
  rebuildMerged();
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

// --- Merged categories: combine multiple sub-categories into one dropdown ---
// Index scheme: sourceIndex * 1000 + originalIndex
export const MERGED_CATEGORIES = {
  '칼슘류': {
    sources: ['식품A', '식품AA', '식품B', '식품C', '식품D'],
    unitMap: { '식품A': 'g', '식품AA': 'g', '식품B': 'g', '식품C': 'g', '식품D': 'g' },
  },
  '비타민': {
    sources: ['식품G', '식품H', '식품HH', '식품I'],
    unitMap: { '식품G': '캡슐', '식품H': 'tsp', '식품HH': 'g', '식품I': '캡슐' },
  },
};

// Reverse lookup: sub-category → merged category key
const SUB_TO_MERGED = {};
for (const [mergedKey, config] of Object.entries(MERGED_CATEGORIES)) {
  for (const src of config.sources) SUB_TO_MERGED[src] = mergedKey;
}

// Build merged effectiveMaps
function rebuildMerged() {
  for (const [mergedKey, config] of Object.entries(MERGED_CATEGORIES)) {
    effectiveMap[mergedKey] = {};
    config.sources.forEach((srcKey, srcIdx) => {
      const srcMap = effectiveMap[srcKey];
      if (!srcMap) return;
      for (const [idx, food] of Object.entries(srcMap)) {
        effectiveMap[mergedKey][srcIdx * 1000 + Number(idx)] = food;
      }
    });
  }
}

// Get source sub-category key from a merged dropdown index
export function getMergedSource(mergedCatKey, dropdownIndex) {
  const config = MERGED_CATEGORIES[mergedCatKey];
  if (!config) return null;
  const srcIdx = Math.floor(dropdownIndex / 1000);
  return config.sources[srcIdx] || null;
}

loadOverrides();

// --- Category labels for UI ---
// Individual sub-category labels (used internally)
const SUB_CATEGORY_LABELS = {
  '식품A': '생뼈류',
  '식품AA': 'RMB',
  '식품B': '본밀류',
  '식품C': '달걀껍질가루',
  '식품D': '기타칼슘',
  '식품G': '비타민B',
  '식품H': '효모(스푼)',
  '식품HH': '효모(g)',
  '식품I': '비타민E',
};

// Public labels: merged + non-merged categories
export const CATEGORY_LABELS = {
  '칼슘류': '칼슘류',
  '식품F': '고기류',
  '식품FF': '내장류',
  '비타민': '비타민',
  '식품J': '타우린(캡슐)',
  '식품JJ': '타우린(mg)',
  '식품K': '오메가3',
  '식품L': '난류',
  '미네랄': '미네랄',
  '식품P': '야채퓨레(채소)',
  '식품Q': '야채퓨레(기타)',
  '식품R': '직접 넣는 데이터',
};

export const ALL_CATEGORY_KEYS = Object.keys(CATEGORY_LABELS);

// --- Public API for UI ---

// Get all items for a category (original + added, excluding deleted)
export function getManagedItems(catKey) {
  // Merged category: combine items from all sub-categories
  const merged = MERGED_CATEGORIES[catKey];
  if (merged) {
    return merged.sources.flatMap(srcKey => getManagedItems(srcKey));
  }

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
  const merged = MERGED_CATEGORIES[catKey];
  if (merged) {
    return merged.sources.flatMap(srcKey => getDeletedItems(srcKey));
  }

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
  const merged = MERGED_CATEGORIES[catKey];
  const actualKey = merged ? merged.sources[0] : catKey;
  const ov = getOverride(actualKey);
  ov.added.push(food);
  saveOverrides();
  rebuildCategory(actualKey);
  if (merged) rebuildMerged();
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
  if (SUB_TO_MERGED[catKey]) rebuildMerged();
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
  if (SUB_TO_MERGED[catKey]) rebuildMerged();
}

// Restore a deleted original
export function restoreFood(catKey, index) {
  const ov = getOverride(catKey);
  if (ov.deleted) {
    ov.deleted = ov.deleted.filter(i => i !== index);
  }
  saveOverrides();
  rebuildCategory(catKey);
  if (SUB_TO_MERGED[catKey]) rebuildMerged();
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
  const merged = MERGED_CATEGORIES[categoryKey];
  if (merged) {
    // For merged categories, include source sub-category label and unit
    const items = Object.entries(catMap).map(([idx, food]) => {
      const mergedIdx = Number(idx);
      const srcIdx = Math.floor(mergedIdx / 1000);
      const srcKey = merged.sources[srcIdx];
      const subLabel = SUB_CATEGORY_LABELS[srcKey] || srcKey;
      return {
        index: mergedIdx,
        name: food.name,
        label: `[${subLabel}] ${food.name}`,
        unit: merged.unitMap?.[srcKey],
      };
    }).sort((a, b) => a.index - b.index);
    return applyOrder(items, categoryKey);
  }
  // Check for per-item unit info from food_data.json
  const catDef = categories[categoryKey];
  const itemUnitMap = {};
  if (catDef) {
    for (const item of catDef.items) {
      if (item.unit) itemUnitMap[item.index] = item.unit;
    }
  }
  const items = Object.entries(catMap).map(([idx, food]) => {
    const numIdx = Number(idx);
    return {
      index: numIdx,
      name: food.name,
      ...(itemUnitMap[numIdx] ? { unit: itemUnitMap[numIdx] } : {}),
    };
  }).sort((a, b) => a.index - b.index);
  return applyOrder(items, categoryKey);
}

// --- Item ordering ---
const ORDER_KEY = 'catfood_item_order';
let itemOrder = {};

function loadItemOrder() {
  try { itemOrder = JSON.parse(localStorage.getItem(ORDER_KEY)) || {}; } catch { itemOrder = {}; }
}

function saveItemOrder() {
  localStorage.setItem(ORDER_KEY, JSON.stringify(itemOrder));
}

loadItemOrder();

// Get custom order for a category (array of indices in desired order)
export function getItemOrder(catKey) {
  return itemOrder[catKey] || null;
}

// Set custom order for a category
export function setItemOrder(catKey, order) {
  itemOrder[catKey] = order;
  saveItemOrder();
}

// Get all order data (for Gist sync)
export function getItemOrderData() {
  return itemOrder;
}

// Set all order data (from Gist sync)
export function setItemOrderData(data) {
  itemOrder = data || {};
  saveItemOrder();
}

// Apply ordering to items list
function applyOrder(items, catKey) {
  const order = itemOrder[catKey];
  if (!order || order.length === 0) return items;
  const orderMap = new Map(order.map((idx, pos) => [idx, pos]));
  return [...items].sort((a, b) => {
    const posA = orderMap.has(a.index) ? orderMap.get(a.index) : 9999;
    const posB = orderMap.has(b.index) ? orderMap.get(b.index) : 9999;
    if (posA !== posB) return posA - posB;
    return a.index - b.index;
  });
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

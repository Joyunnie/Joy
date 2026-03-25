import rawData from '../../food_data.json';

export const foods = rawData.foods;
export const categories = rawData.categories;

// Build lookup maps: categoryKey -> { index -> food }
const categoryFoodMap = {};
for (const [catKey, catVal] of Object.entries(categories)) {
  categoryFoodMap[catKey] = {};
  for (const item of catVal.items) {
    const food = foods.find(f => f.name === item.name);
    if (food) {
      categoryFoodMap[catKey][item.index] = food;
    }
  }
}

// Water is a special slot - always "물"
const waterFood = foods.find(f => f.name === '물' && f.id === '0');

// --- 식품R management ---
// Original 식품R items from food_data.json (immutable reference)
const ORIGINAL_R_ITEMS = categories['식품R'] ? [...categories['식품R'].items] : [];
const originalRFoods = {}; // index -> food object (from food_data.json)
for (const item of ORIGINAL_R_ITEMS) {
  const food = foods.find(f => f.name === item.name);
  if (food) {
    originalRFoods[item.index] = { name: food.name, nutrients: { ...food.nutrients } };
  }
}

// localStorage keys
const R_FOODS_KEY = 'catfood_r_foods'; // overrides for original 식품R items
const CUSTOM_FOODS_KEY = 'catfood_custom_foods'; // user-added new items

// rFoods: merged 식품R data (original + overrides from localStorage)
// Key: original index (2-11), Value: food object or null (deleted)
let rFoodOverrides = {};
let customFoods = [];
const foodLookupMap = {}; // dropdown index -> food object for 식품R

function loadAllFoods() {
  // Load overrides for original 식품R items
  try {
    rFoodOverrides = JSON.parse(localStorage.getItem(R_FOODS_KEY)) || {};
  } catch { rFoodOverrides = {}; }

  // Load user-added custom foods
  try {
    customFoods = JSON.parse(localStorage.getItem(CUSTOM_FOODS_KEY)) || [];
  } catch { customFoods = []; }

  rebuildLookup();
}

function rebuildLookup() {
  Object.keys(foodLookupMap).forEach(k => delete foodLookupMap[k]);

  // Original 식품R items (with possible overrides/deletions)
  for (const item of ORIGINAL_R_ITEMS) {
    if (rFoodOverrides[item.index] === null) continue; // deleted
    if (rFoodOverrides[item.index]) {
      foodLookupMap[item.index] = rFoodOverrides[item.index];
    } else {
      foodLookupMap[item.index] = originalRFoods[item.index];
    }
  }

  // Custom foods: index >= 100
  customFoods.forEach((cf, i) => {
    foodLookupMap[100 + i] = cf;
  });
}

loadAllFoods();

// Get all manageable foods (original 식품R + custom) for the UI
export function getAllManagedFoods() {
  const result = [];
  // Original 식품R items
  for (const item of ORIGINAL_R_ITEMS) {
    if (rFoodOverrides[item.index] === null) continue; // deleted
    const food = rFoodOverrides[item.index] || originalRFoods[item.index];
    if (food) {
      result.push({ type: 'original', index: item.index, ...food });
    }
  }
  // Custom foods
  customFoods.forEach((cf, i) => {
    result.push({ type: 'custom', index: i, ...cf });
  });
  return result;
}

// Get deleted original items (for potential restore)
export function getDeletedOriginals() {
  const result = [];
  for (const item of ORIGINAL_R_ITEMS) {
    if (rFoodOverrides[item.index] === null) {
      const orig = originalRFoods[item.index];
      if (orig) result.push({ index: item.index, name: orig.name });
    }
  }
  return result;
}

// Update an original 식품R item
export function updateOriginalRFood(index, food) {
  rFoodOverrides[index] = food;
  localStorage.setItem(R_FOODS_KEY, JSON.stringify(rFoodOverrides));
  rebuildLookup();
  // Also update the categoryFoodMap so getFoodByCategory picks it up
  if (categoryFoodMap['식품R']) {
    categoryFoodMap['식품R'][index] = food;
  }
}

// Delete an original 식품R item
export function deleteOriginalRFood(index) {
  rFoodOverrides[index] = null; // mark as deleted
  localStorage.setItem(R_FOODS_KEY, JSON.stringify(rFoodOverrides));
  rebuildLookup();
  if (categoryFoodMap['식품R']) {
    delete categoryFoodMap['식품R'][index];
  }
}

// Restore a deleted original 식품R item
export function restoreOriginalRFood(index) {
  delete rFoodOverrides[index];
  localStorage.setItem(R_FOODS_KEY, JSON.stringify(rFoodOverrides));
  rebuildLookup();
  if (categoryFoodMap['식품R'] && originalRFoods[index]) {
    categoryFoodMap['식품R'][index] = originalRFoods[index];
  }
}

// Custom food CRUD
export function getCustomFoods() {
  return customFoods;
}

export function addCustomFood(food) {
  customFoods = [...customFoods, food];
  localStorage.setItem(CUSTOM_FOODS_KEY, JSON.stringify(customFoods));
  rebuildLookup();
}

export function updateCustomFood(index, food) {
  customFoods = customFoods.map((cf, i) => i === index ? food : cf);
  localStorage.setItem(CUSTOM_FOODS_KEY, JSON.stringify(customFoods));
  rebuildLookup();
}

export function removeCustomFood(index) {
  customFoods = customFoods.filter((_, i) => i !== index);
  localStorage.setItem(CUSTOM_FOODS_KEY, JSON.stringify(customFoods));
  rebuildLookup();
}

export function getFoodByCategory(categoryKey, dropdownIndex) {
  if (!dropdownIndex || dropdownIndex <= 1) return null;
  if (categoryKey === 'water') return waterFood;
  // 식품R: check merged lookup
  if (categoryKey === '식품R') {
    return foodLookupMap[dropdownIndex] || null;
  }
  const catMap = categoryFoodMap[categoryKey];
  if (!catMap) return null;
  return catMap[dropdownIndex] || null;
}

export function getCategoryItems(categoryKey) {
  const cat = categories[categoryKey];
  if (!cat) return [];

  if (categoryKey === '식품R') {
    const items = [];
    // Original items (excluding deleted)
    for (const item of ORIGINAL_R_ITEMS) {
      if (rFoodOverrides[item.index] === null) continue;
      const food = rFoodOverrides[item.index] || originalRFoods[item.index];
      items.push({ index: item.index, name: food ? food.name : item.name });
    }
    // Custom foods
    customFoods.forEach((cf, i) => {
      items.push({ index: 100 + i, name: cf.name });
    });
    return items;
  }

  return [...cat.items];
}

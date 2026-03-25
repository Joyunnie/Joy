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

// Custom foods registry (added by user, stored in localStorage)
const CUSTOM_FOODS_KEY = 'catfood_custom_foods';
let customFoods = [];
const customFoodMap = {}; // index -> food object

function loadCustomFoods() {
  try {
    customFoods = JSON.parse(localStorage.getItem(CUSTOM_FOODS_KEY)) || [];
  } catch { customFoods = []; }
  // Rebuild map
  for (const [idx, cf] of Object.entries(customFoods)) {
    const startIndex = 100 + Number(idx);
    customFoodMap[startIndex] = cf;
  }
}
loadCustomFoods();

export function getCustomFoods() {
  return customFoods;
}

export function addCustomFood(food) {
  customFoods = [...customFoods, food];
  localStorage.setItem(CUSTOM_FOODS_KEY, JSON.stringify(customFoods));
  const idx = 100 + customFoods.length - 1;
  customFoodMap[idx] = food;
}

export function updateCustomFood(index, food) {
  customFoods = customFoods.map((cf, i) => i === index ? food : cf);
  localStorage.setItem(CUSTOM_FOODS_KEY, JSON.stringify(customFoods));
  customFoodMap[100 + index] = food;
}

export function removeCustomFood(index) {
  customFoods = customFoods.filter((_, i) => i !== index);
  localStorage.setItem(CUSTOM_FOODS_KEY, JSON.stringify(customFoods));
  // Rebuild map
  Object.keys(customFoodMap).forEach(k => delete customFoodMap[k]);
  customFoods.forEach((cf, i) => { customFoodMap[100 + i] = cf; });
}

export function getFoodByCategory(categoryKey, dropdownIndex) {
  if (!dropdownIndex || dropdownIndex <= 1) return null;
  if (categoryKey === 'water') return waterFood;
  // Check custom foods for 식품R category
  if (categoryKey === '식품R' && dropdownIndex >= 100) {
    return customFoodMap[dropdownIndex] || null;
  }
  const catMap = categoryFoodMap[categoryKey];
  if (!catMap) return null;
  return catMap[dropdownIndex] || null;
}

export function getCategoryItems(categoryKey) {
  const cat = categories[categoryKey];
  if (!cat) return [];
  const items = [...cat.items];
  // Append custom foods to 식품R
  if (categoryKey === '식품R') {
    customFoods.forEach((cf, i) => {
      items.push({ index: 100 + i, name: cf.name });
    });
  }
  return items;
}

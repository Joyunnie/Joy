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

export function getFoodByCategory(categoryKey, dropdownIndex) {
  if (!dropdownIndex || dropdownIndex <= 1) return null;
  if (categoryKey === 'water') return waterFood;
  const catMap = categoryFoodMap[categoryKey];
  if (!catMap) return null;
  return catMap[dropdownIndex] || null;
}

export function getCategoryItems(categoryKey) {
  const cat = categories[categoryKey];
  if (!cat) return [];
  return cat.items;
}

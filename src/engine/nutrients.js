import { getFoodByCategory } from '../data/foodData';
import { SLOT_DEFS, nrc } from '../data/appConfig';

// All nutrient keys (excluding 함량(g))
export const NUTRIENT_KEYS = [
  '칼로리(Kcal)', '수분(g)', '단백질(g)', '지방(g)',
  '비타민A(mcg)', '비타민B1(mg)', '비타민B2(mg)', '비타민B6(mg)',
  '나이아신(mg)', '판토텐산(mg)', '비타민B12(mcg)', '폴산(mcg)',
  '칼슘(mg)', '인(mg)', '마그네슘(mg)', '나트륨(mg)', '칼륨(mg)',
  '철(mg)', '구리(mg)', '아연(mg)', '망간(mg)', '셀레늄(mcg)', '요오드(mcg)',
  '이소루신(mg)', '루신(mg)', '라이신(mg)', '메티오닌(mg)', '시스테인(mg)',
  '페닐알라린(mg)', '티로신(mg)', '트레오닌(mg)', '트립토판(mg)', '발린(mg)',
  '히스티딘(mg)', '아르기닌(mg)', '알라닌(mg)', '아스파르트산(mg)',
  '글루탐산(mg)', '글리신(mg)', '프롤린(mg)', '세린(mg)',
  '총지방산(mg)', '포화지방산(mg)', '불포화지방산(mg)', '콜레스테롤(mg)',
  'n-3(mg)', 'n-6(mg)', '리놀레산(mg)', '알파리놀렌산(mg)', 'EPA(mg)', 'DHA(mg)',
  '타우린(mg)', '비타민D(mcg)', '비타민E(mg)', '비타민K(mcg)', '탄수화물(g)',
];

// Calculate total nutrients across all slots
export function calcTotalNutrients(slotStates, omega3Custom) {
  const totals = {};
  for (const key of NUTRIENT_KEYS) {
    totals[key] = 0;
  }

  let totalGrams = 0;

  for (const def of SLOT_DEFS) {
    const state = slotStates[def.id];
    if (!state) continue;

    const { dropdown, amount } = state;
    if (!amount || amount <= 0) continue;
    if (!dropdown || dropdown <= 1) continue;

    let food = getFoodByCategory(def.category, dropdown);
    if (!food) continue;

    // Apply omega3 custom nutrients if this is "나의 오메가3 영양제(겔)"
    let nutrients = food.nutrients;
    if (food.name === '나의 오메가3 영양제(겔)' && omega3Custom) {
      nutrients = { ...food.nutrients };
      if (omega3Custom.calories != null && omega3Custom.calories !== '') {
        nutrients['칼로리(Kcal)'] = Number(omega3Custom.calories) * 100;
      }
      if (omega3Custom.fat != null && omega3Custom.fat !== '') {
        nutrients['지방(g)'] = Number(omega3Custom.fat) * 100;
      }
      if (omega3Custom.epa != null && omega3Custom.epa !== '') {
        nutrients['EPA(mg)'] = Number(omega3Custom.epa) * 100;
      }
      if (omega3Custom.dha != null && omega3Custom.dha !== '') {
        nutrients['DHA(mg)'] = Number(omega3Custom.dha) * 100;
      }
      if (omega3Custom.vitE != null && omega3Custom.vitE !== '') {
        nutrients['비타민E(mg)'] = Number(omega3Custom.vitE) * 100;
      }
      // n-3 = EPA + DHA + other omega3
      const epa = omega3Custom.epa ? Number(omega3Custom.epa) : (food.nutrients['EPA(mg)'] || 0) / 100;
      const dha = omega3Custom.dha ? Number(omega3Custom.dha) : (food.nutrients['DHA(mg)'] || 0) / 100;
      const other = omega3Custom.otherOmega3 ? Number(omega3Custom.otherOmega3) : 0;
      if (omega3Custom.epa || omega3Custom.dha || omega3Custom.otherOmega3) {
        nutrients['n-3(mg)'] = (epa + dha + other) * 100;
      }
    }

    // All data is per 100 units, so nutrient = (value / 100) * amount
    for (const key of NUTRIENT_KEYS) {
      const val = nutrients[key];
      if (typeof val === 'number') {
        totals[key] += (val / 100) * amount;
      }
    }

    // Count grams for total weight
    if (def.unit === 'g') {
      totalGrams += amount;
    }
  }

  totals._totalGrams = totalGrams;
  return totals;
}

// Daily nutrients = total / recipeDays
export function calcDailyNutrients(totals, recipeDays) {
  if (!recipeDays || recipeDays <= 0) return totals;
  const daily = {};
  for (const key of NUTRIENT_KEYS) {
    daily[key] = (totals[key] || 0) / recipeDays;
  }
  daily._totalGrams = (totals._totalGrams || 0);
  daily._dailyGrams = (totals._totalGrams || 0) / recipeDays;
  return daily;
}

// DM% = nutrientGrams / (totalDailyGrams - waterGrams) * 100
export function calcDMPercent(nutrientGrams, dailyGrams, waterGrams) {
  const dm = dailyGrams - waterGrams;
  if (dm <= 0) return 0;
  return (nutrientGrams / dm) * 100;
}

// Sufficiency% = dailyAmount / (nrcValue/1000 * dailyCalories)
export function calcSufficiency(dailyAmount, nrcValue, dailyCalories) {
  if (nrcValue == null || nrcValue === 0 || !dailyCalories) return null;
  const requirement = (nrcValue / 1000) * dailyCalories;
  if (requirement <= 0) return null;
  return dailyAmount / requirement;
}

// Get NRC value based on kitten/adult
export function getNrcValue(nrcEntry, isKitten) {
  if (!nrcEntry) return null;
  if (isKitten) {
    return nrcEntry['자묘'] != null ? nrcEntry['자묘'] : nrcEntry['성묘'];
  }
  return nrcEntry['성묘'] != null ? nrcEntry['성묘'] : null;
}

// Get upper limit
export function getNrcUpperLimit(nrcEntry, isKitten) {
  if (!nrcEntry) return null;
  if (isKitten) {
    return nrcEntry['상한_자묘'] ?? nrcEntry['상한'] ?? null;
  }
  return nrcEntry['상한_성묘'] ?? nrcEntry['상한'] ?? null;
}

// Calculate ratios
export function calcRatios(slotStates) {
  const getAmt = (id) => {
    const s = slotStates[id];
    return (s && s.amount > 0 && s.dropdown > 1) ? s.amount : 0;
  };
  const getAmtRaw = (id) => {
    const s = slotStates[id];
    return (s && s.amount > 0) ? s.amount : 0;
  };

  const rawBone = getAmt('calcium_0'); // 생뼈류
  const rmb = getAmt('calcium_3'); // RMB

  let meatTotal = 0;
  for (let i = 0; i < 9; i++) meatTotal += getAmt(`meat_${i}`);

  let organTotal = 0;
  for (let i = 0; i < 5; i++) organTotal += getAmt(`organ_${i}`);

  let veggieTotal = 0;
  for (let i = 0; i < 13; i++) veggieTotal += getAmt(`veggie_${i}`);

  let otherVegTotal = 0;
  for (let i = 0; i < 7; i++) otherVegTotal += getAmt(`otherVeg_${i}`);

  // 뼈:살 비율 = (생뼈 + RMB×0.6) / (생뼈 + RMB + 고기류 + 내장류)
  const boneMeatDenom = rawBone + rmb + meatTotal + organTotal;
  const boneRatio = boneMeatDenom > 0 ? (rawBone + rmb * 0.6) / boneMeatDenom : 0;

  // 내장:육류 비율 = 내장 / (생뼈 + 고기류 + 내장류)
  const organDenom = rawBone + meatTotal + organTotal;
  const organRatio = organDenom > 0 ? organTotal / organDenom : 0;

  // 퓨레:육류 비율 = (채소 + 기타야채) / (생뼈 + RMB + 고기류 + 내장류 + 채소 + 기타야채)
  const pureeTotal = veggieTotal + otherVegTotal;
  const pureeDenom = rawBone + rmb + meatTotal + organTotal + pureeTotal;
  const pureeRatio = pureeDenom > 0 ? pureeTotal / pureeDenom : 0;

  return { boneRatio, organRatio, pureeRatio };
}

// NRC key mapping: nutrient display name -> NRC category + key
export const NRC_MAPPING = {
  '단백질(g)': { cat: '기본영양', key: '단백질' },
  '지방(g)': { cat: '기본영양', key: '지방' },
  '칼슘(mg)': { cat: '기본영양', key: '칼슘' },
  '인(mg)': { cat: '기본영양', key: '인' },
  '비타민A(mcg)': { cat: '기본영양', key: '비타민A' },
  '비타민B1(mg)': { cat: '기본영양', key: '비타민B1' },
  '비타민B2(mg)': { cat: '기본영양', key: '비타민B2' },
  '비타민B6(mg)': { cat: '기본영양', key: '비타민B6' },
  '나이아신(mg)': { cat: '기본영양', key: '나이아신' },
  '판토텐산(mg)': { cat: '기본영양', key: '판토텐산' },
  '비타민B12(mcg)': { cat: '기본영양', key: '비타민B12' },
  '폴산(mcg)': { cat: '기본영양', key: '폴산' },
  '비타민D(mcg)': { cat: '기본영양', key: '비타민D' },
  '비타민E(mg)': { cat: '기본영양', key: '비타민E' },
  '비타민K(mcg)': { cat: '기본영양', key: '비타민K' },
  '마그네슘(mg)': { cat: '무기질', key: '마그네슘' },
  '나트륨(mg)': { cat: '무기질', key: '나트륨' },
  '칼륨(mg)': { cat: '무기질', key: '칼륨' },
  '철(mg)': { cat: '무기질', key: '철' },
  '구리(mg)': { cat: '무기질', key: '구리' },
  '아연(mg)': { cat: '무기질', key: '아연' },
  '망간(mg)': { cat: '무기질', key: '망간' },
  '셀레늄(mcg)': { cat: '무기질', key: '셀레늄' },
  '요오드(mcg)': { cat: '무기질', key: '요오드' },
  '이소루신(mg)': { cat: '아미노산', key: '이소루신' },
  '루신(mg)': { cat: '아미노산', key: '루신' },
  '라이신(mg)': { cat: '아미노산', key: '라이신' },
  '메티오닌(mg)': { cat: '아미노산', key: '메티오닌' },
  '시스테인(mg)': { cat: '아미노산', key: '시스테인' },
  '페닐알라린(mg)': { cat: '아미노산', key: '페닐알라린' },
  '티로신(mg)': { cat: '아미노산', key: '티로신' },
  '트레오닌(mg)': { cat: '아미노산', key: '트레오닌' },
  '트립토판(mg)': { cat: '아미노산', key: '트립토판' },
  '발린(mg)': { cat: '아미노산', key: '발린' },
  '히스티딘(mg)': { cat: '아미노산', key: '히스티딘' },
  '아르기닌(mg)': { cat: '아미노산', key: '아르기닌' },
  '타우린(mg)': { cat: '아미노산', key: '타우린' },
  '글루탐산(mg)': { cat: '아미노산', key: '글루탐산' },
  '리놀레산(mg)': { cat: '지방산', key: '리놀레산' },
  '알파리놀렌산(mg)': { cat: '지방산', key: '알파리놀렌산' },
  'EPA(mg)': { cat: '지방산', key: 'EPA' },
  'DHA(mg)': { cat: '지방산', key: 'DHA' },
};

export function getNrcEntry(nutrientKey) {
  const mapping = NRC_MAPPING[nutrientKey];
  if (!mapping) return null;
  return nrc[mapping.cat]?.[mapping.key] || null;
}

// Calculate all sufficiency values
export function calcAllSufficiency(daily, dailyCalories, isKitten) {
  const result = {};
  for (const [nutrientKey, mapping] of Object.entries(NRC_MAPPING)) {
    const nrcEntry = nrc[mapping.cat]?.[mapping.key];
    if (!nrcEntry) continue;
    const nrcVal = getNrcValue(nrcEntry, isKitten);
    if (nrcVal == null) continue;
    const suff = calcSufficiency(daily[nutrientKey] || 0, nrcVal, dailyCalories);
    if (suff != null) {
      result[nutrientKey] = suff;
    }
  }
  // EPA+DHA combined
  const epaDhaEntry = nrc['지방산']?.['EPA+DHA'];
  if (epaDhaEntry) {
    const nrcVal = epaDhaEntry['성묘'];
    if (nrcVal) {
      const combined = (daily['EPA(mg)'] || 0) + (daily['DHA(mg)'] || 0);
      const suff = calcSufficiency(combined, nrcVal, dailyCalories);
      if (suff != null) result['EPA+DHA'] = suff;
    }
  }
  return result;
}

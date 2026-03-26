import { nrc } from '../data/appConfig';
import { getNrcValue, getNrcUpperLimit, calcSufficiency, calcDMPercent, NRC_MAPPING } from './nutrients';

const AMINO_ACID_KEYS = new Set([
  '이소루신(mg)', '루신(mg)', '라이신(mg)', '메티오닌(mg)', '시스테인(mg)',
  '페닐알라린(mg)', '티로신(mg)', '트레오닌(mg)', '트립토판(mg)', '발린(mg)',
  '히스티딘(mg)', '아르기닌(mg)', '알라닌(mg)', '아스파르트산(mg)',
  '글루탐산(mg)', '글리신(mg)', '프롤린(mg)', '세린(mg)',
]);

export function generateWarnings(daily, dailyCalories, isKitten, slotStates, nutrientAdjust) {
  const warnings = [];

  if (!daily || !dailyCalories) return warnings;

  const dailyGrams = daily._dailyGrams || 0;
  const waterG = daily['수분(g)'] || 0;

  // 1. Low calories
  const actualCal = daily['칼로리(Kcal)'] || 0;
  if (actualCal < dailyCalories && actualCal > 0) {
    warnings.push({ type: 'red', msg: '▶칼로리 낮음' });
  }

  // 2. Water deficiency
  const carbs = daily['탄수화물(g)'] || 0;
  const fat = daily['지방(g)'] || 0;
  const protein = daily['단백질(g)'] || 0;
  const totalWater = carbs * 0.6 + fat * 1.08 + protein * 0.36 + waterG;
  const requiredWater = dailyCalories * 0.9;
  if (totalWater < requiredWater && dailyGrams > 0) {
    const deficit = requiredWater - totalWater;
    warnings.push({
      type: 'blue',
      msg: '▶수분 추가섭취 필요',
      detail: `하루필요 수분량 ${requiredWater.toFixed(1)}g중 ${deficit.toFixed(1)}g의 추가 음수 필요`,
    });
  }

  // 3. Calcium DM% > 4%
  const calciumMg = daily['칼슘(mg)'] || 0;
  const calciumG = calciumMg / 1000;
  const dryMatter = dailyGrams - waterG;
  const calciumDmRatio = dryMatter > 0 ? calciumG / dryMatter : 0;
  if (calciumDmRatio > 0.04) {
    warnings.push({ type: 'red', msg: '▶칼슘 DM% 높음' });
  }

  // 4. Ca:P ratio
  const phosphorusMg = daily['인(mg)'] || 0;
  if (phosphorusMg > 0) {
    const caPRatio = calciumMg / phosphorusMg;
    if (caPRatio < 0.5) {
      warnings.push({ type: 'red', msg: '▶칼슘 비율 낮음' });
    }
    if (caPRatio > 1.5) {
      warnings.push({ type: 'red', msg: '▶칼슘 비율 높음' });
    }
  }

  // 5. Upper limit warnings for all nutrients with NRC upper limits
  for (const [nutrientKey, mapping] of Object.entries(NRC_MAPPING)) {
    // 성묘일 때 아미노산 경고 숨김 (타우린 제외)
    if (!isKitten && AMINO_ACID_KEYS.has(nutrientKey)) continue;
    const entry = nrc[mapping.cat]?.[mapping.key];
    if (!entry) continue;
    const upperLimit = getNrcUpperLimit(entry, isKitten);
    if (upperLimit == null) continue;
    const dailyAmount = daily[nutrientKey] || 0;
    const upperRequirement = (upperLimit / 1000) * dailyCalories;
    if (upperRequirement > 0 && dailyAmount > upperRequirement) {
      warnings.push({ type: 'red', msg: `▶${mapping.key} 높음`, nutrientKey });
    }
  }

  // 6. Vitamin K fish base warning
  const vitKEntry = nrc['기본영양']?.['비타민K'];
  if (vitKEntry) {
    const nrcVal = getNrcValue(vitKEntry, isKitten);
    if (nrcVal) {
      const suff = calcSufficiency(daily['비타민K(mcg)'] || 0, nrcVal, dailyCalories);
      if (suff != null && suff < 1) {
        warnings.push({ type: 'red', msg: '▶생선베이스 일 때 주의' });
      }
    }
  }

  // 7. Nutrient adjustment (DM%) warnings
  if (nutrientAdjust) {
    const adjustMap = {
      protein: { key: '단백질(g)', label: '단백질' },
      fat: { key: '지방(g)', label: '지방' },
      calcium: { key: '칼슘(mg)', label: '칼슘', isMg: true },
      phosphorus: { key: '인(mg)', label: '인', isMg: true },
      sodium: { key: '나트륨(mg)', label: '나트륨', isMg: true },
    };

    for (const [field, info] of Object.entries(adjustMap)) {
      const target = nutrientAdjust[field];
      if (!target || target <= 0) continue;
      const val = daily[info.key] || 0;
      const valG = info.isMg ? val / 1000 : val;
      const dm = calcDMPercent(valG, dailyGrams, waterG);
      if (dm > target) {
        warnings.push({ type: 'red', msg: `▶조절 ${info.label} 초과` });
      }
    }
  }

  return warnings;
}

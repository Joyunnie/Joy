export function calcCalories(type, weight, expectedWeight) {
  switch (type) {
    case 1: return 110 * Math.pow(weight, 0.4);
    case 2: return 110 * Math.pow(weight, 0.4) * 0.9;
    case 3: return 100 * Math.pow(weight, 0.67);
    case 4: return 130 * Math.pow(weight, 0.4);
    case 5: return 100 * Math.pow(weight, 0.67) * 6.732 * (Math.exp(-0.189 * weight / expectedWeight) - 0.66) * 0.9;
    case 6: return 100 * Math.pow(weight, 0.67) * 6.732 * (Math.exp(-0.189 * weight / expectedWeight) - 0.66);
    default: return 0;
  }
}

export const CALORIE_LABELS = [
  { value: 1, label: '중성화 되지 않은 마른 고양이' },
  { value: 2, label: '중성화된 마른 고양이' },
  { value: 3, label: '중성화된 비만 고양이' },
  { value: 4, label: '중성화 되지 않은 비만 고양이' },
  { value: 5, label: '중성화 된 자묘' },
  { value: 6, label: '중성화 되지 않은 자묘' },
];

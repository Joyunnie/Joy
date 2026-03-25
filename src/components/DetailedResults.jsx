const fmt = (v) => v != null && !isNaN(v) ? v.toFixed(1) : '-';
const fmtPct = (v) => v != null && !isNaN(v) ? `${Math.round(v * 100)}%` : '-';

const aminoAcidKeys = [
  { key: '이소루신(mg)', label: '이소루신' },
  { key: '루신(mg)', label: '루신' },
  { key: '라이신(mg)', label: '라이신' },
  { key: '메티오닌(mg)', label: '메티오닌' },
  { key: '시스테인(mg)', label: '시스테인' },
  { key: '페닐알라린(mg)', label: '페닐알라린' },
  { key: '티로신(mg)', label: '티로신' },
  { key: '트레오닌(mg)', label: '트레오닌' },
  { key: '트립토판(mg)', label: '트립토판' },
  { key: '발린(mg)', label: '발린' },
  { key: '히스티딘(mg)', label: '히스티딘' },
  { key: '아르기닌(mg)', label: '아르기닌' },
  { key: '알라닌(mg)', label: '알라닌' },
  { key: '아스파르트산(mg)', label: '아스파르트산' },
  { key: '글루탐산(mg)', label: '글루탐산' },
  { key: '글리신(mg)', label: '글리신' },
  { key: '프롤린(mg)', label: '프롤린' },
  { key: '세린(mg)', label: '세린' },
  { key: '타우린(mg)', label: '타우린' },
];

const fattyAcidKeys = [
  { key: '총지방산(mg)', label: '총 지방산', unit: 'mg' },
  { key: '포화지방산(mg)', label: '포화지방산', unit: 'mg' },
  { key: '불포화지방산(mg)', label: '불포화지방산', unit: 'mg' },
  { key: '콜레스테롤(mg)', label: '콜레스테롤', unit: 'mg' },
  { key: 'n-3(mg)', label: 'n-3', unit: 'mg' },
  { key: 'n-6(mg)', label: 'n-6', unit: 'mg' },
  { key: '_n3n6ratio', label: 'n-3:n-6 비율', unit: '', isRatio: true },
  { key: '리놀레산(mg)', label: '리놀레산', unit: 'mg' },
  { key: '알파리놀렌산(mg)', label: '알파-리놀렌산', unit: 'mg' },
  { key: 'EPA(mg)', label: 'EPA', unit: 'mg' },
  { key: 'DHA(mg)', label: 'DHA', unit: 'mg' },
  { key: '_epaDha', label: 'EPA+DHA', unit: 'mg', isComputed: true },
  { key: '_epaDhaRatio', label: 'EPA:DHA 비율', unit: '', isRatio: true },
];

export default function DetailedResults({ daily, sufficiency, slotStates }) {
  if (!daily) return null;

  const getSuff = (key) => sufficiency[key] != null ? fmtPct(sufficiency[key]) : '-';

  const epa = daily['EPA(mg)'] || 0;
  const dha = daily['DHA(mg)'] || 0;
  const n3 = daily['n-3(mg)'] || 0;
  const n6 = daily['n-6(mg)'] || 0;

  // Ratios
  const getAmt = (id) => {
    const s = slotStates[id];
    return (s && s.amount > 0 && s.dropdown > 1) ? s.amount : 0;
  };

  const rawBone = getAmt('calcium_0');
  const rmb = getAmt('calcium_3');
  let meatTotal = 0;
  for (let i = 0; i < 9; i++) meatTotal += getAmt(`meat_${i}`);
  let organTotal = 0;
  for (let i = 0; i < 5; i++) organTotal += getAmt(`organ_${i}`);
  let veggieTotal = 0;
  for (let i = 0; i < 13; i++) veggieTotal += getAmt(`veggie_${i}`);
  let otherVegTotal = 0;
  for (let i = 0; i < 7; i++) otherVegTotal += getAmt(`otherVeg_${i}`);

  const organDenom = rawBone + meatTotal + organTotal;
  const organRatio = organDenom > 0 ? (organTotal / organDenom) * 100 : 0;

  const pureeTotal = veggieTotal + otherVegTotal;
  const pureeDenom = rawBone + rmb + meatTotal + organTotal + pureeTotal;
  const pureeRatio = pureeDenom > 0 ? (pureeTotal / pureeDenom) * 100 : 0;

  return (
    <div className="space-y-3">
      {/* Amino Acids */}
      <div className="bg-white rounded-lg p-3 shadow-sm border">
        <h3 className="font-bold text-sm mb-2 text-gray-800">아미노산</h3>
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-300">
              <th className="text-xs text-left py-0.5">항목</th>
              <th className="text-xs text-right py-0.5">mg</th>
              <th className="text-xs text-right py-0.5">과부족%</th>
            </tr>
          </thead>
          <tbody>
            {aminoAcidKeys.map(({ key, label }) => (
              <tr key={key} className="border-b border-gray-100">
                <td className="text-xs py-0.5">{label}</td>
                <td className="text-xs py-0.5 text-right">{fmt(daily[key])}</td>
                <td className="text-xs py-0.5 text-right">{getSuff(key)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Fatty Acids */}
      <div className="bg-white rounded-lg p-3 shadow-sm border">
        <h3 className="font-bold text-sm mb-2 text-gray-800">지방산</h3>
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-300">
              <th className="text-xs text-left py-0.5">항목</th>
              <th className="text-xs text-right py-0.5">값</th>
              <th className="text-xs text-right py-0.5">과부족%</th>
            </tr>
          </thead>
          <tbody>
            {fattyAcidKeys.map(({ key, label, unit, isRatio, isComputed }) => {
              let val, suff;
              if (key === '_n3n6ratio') {
                val = n6 > 0 ? fmt(n3 / n6) : '-';
                suff = '-';
              } else if (key === '_epaDha') {
                val = fmt(epa + dha);
                suff = sufficiency['EPA+DHA'] != null ? fmtPct(sufficiency['EPA+DHA']) : '-';
              } else if (key === '_epaDhaRatio') {
                val = dha > 0 ? fmt(epa / dha) : '-';
                suff = '-';
              } else {
                val = fmt(daily[key]);
                suff = getSuff(key);
              }
              return (
                <tr key={key} className="border-b border-gray-100">
                  <td className="text-xs py-0.5">{label}</td>
                  <td className="text-xs py-0.5 text-right">{val}{unit && !isRatio ? <span className="text-gray-400 ml-0.5">{unit}</span> : ''}</td>
                  <td className="text-xs py-0.5 text-right">{suff}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Ratios */}
      <div className="bg-white rounded-lg p-3 shadow-sm border">
        <h3 className="font-bold text-sm mb-2 text-gray-800">비율 정보</h3>
        <div className="space-y-1 text-xs">
          <div className="flex justify-between">
            <span>내장:육류 비율</span>
            <span className="font-semibold">{organRatio.toFixed(1)}%</span>
          </div>
          <div className="flex justify-between">
            <span>퓨레:육류 비율</span>
            <span className="font-semibold">{pureeRatio.toFixed(1)}%</span>
          </div>
        </div>
      </div>
    </div>
  );
}

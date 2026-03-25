import { calcDMPercent } from '../engine/nutrients';

const fmt = (v) => v != null && !isNaN(v) ? v.toFixed(1) : '-';
const fmtPct = (v) => v != null && !isNaN(v) ? `${Math.round(v * 100)}%` : '-';

// New color logic: red if <100% (deficient) or upper limit exceeded, green if ok
function suffColor(v, isUpperExceeded) {
  if (v == null || isNaN(v)) return 'text-gray-400';
  const pct = Math.round(v * 100);
  if (pct === 0) return 'text-gray-400';
  if (pct < 100) return 'text-red-600';
  if (isUpperExceeded) return 'text-red-600 font-bold';
  return 'text-green-600';
}

function Row({ label, value, unit, dm, sufficiency, suffRaw, isUpperExceeded, warning }) {
  const suffClass = suffColor(suffRaw, isUpperExceeded);
  return (
    <tr className="border-b border-gray-100">
      <td className="text-[10px] py-0 pr-1">{label}</td>
      <td className="text-[10px] py-0 text-right pr-0.5">{value}{unit && <span className="text-gray-400 ml-0.5">{unit}</span>}</td>
      <td className="text-[10px] py-0 text-right pr-0.5 text-gray-500">{dm || ''}</td>
      <td className={`text-[10px] py-0 text-right pr-0.5 ${suffClass}`}>{sufficiency || ''}</td>
      <td className="text-[10px] py-0">{warning && <span className="text-red-600 font-bold">{warning}</span>}</td>
    </tr>
  );
}

export default function ResultPanel({ daily, totals, dailyCalories, sufficiency, warnings, slotStates }) {
  if (!daily) return <div className="bg-white rounded p-1.5 shadow-sm border"><p className="text-[10px] text-gray-400">데이터를 입력하세요</p></div>;

  const upperExceeded = sufficiency._upperExceeded || {};
  const isUE = (key) => !!upperExceeded[key];

  const dailyGrams = daily._dailyGrams || 0;
  const totalGrams = daily._totalGrams || 0;
  const waterG = daily['수분(g)'] || 0;
  const dryMatter = dailyGrams - waterG;

  const dmPct = (nutrientG) => {
    const v = calcDMPercent(nutrientG, dailyGrams, waterG);
    return v > 0 ? `${v.toFixed(1)}%` : '';
  };

  const getSuff = (key) => sufficiency[key] != null ? fmtPct(sufficiency[key]) : '-';
  const getSuffRaw = (key) => sufficiency[key] != null ? sufficiency[key] : null;

  const calcium = daily['칼슘(mg)'] || 0;
  const phosphorus = daily['인(mg)'] || 0;

  const getAmt = (id) => {
    const s = slotStates[id];
    return (s && s.amount > 0) ? s.amount : 0;
  };
  const rawBone = getAmt('calcium_0');
  const rmb = getAmt('calcium_3');
  let meatTotal = 0;
  for (let i = 0; i < 9; i++) meatTotal += getAmt(`meat_${i}`);
  let organTotal = 0;
  for (let i = 0; i < 5; i++) organTotal += getAmt(`organ_${i}`);
  const bonePart = rawBone + rmb * 0.6;
  const boneDenom = rawBone + rmb + meatTotal + organTotal;
  const bonePct = boneDenom > 0 ? (bonePart / boneDenom) * 100 : 0;
  const meatPct = boneDenom > 0 ? 100 - bonePct : 0;

  // Calcium DM% > 4% special check
  const calciumDmRatio = dryMatter > 0 ? ((calcium / 1000) / dryMatter) : 0;

  // Find per-nutrient warning from warnings array
  const findWarning = (key) => {
    if (isUE(key)) return warnings.find(w => w.msg?.includes('높음') && w.nutrientKey === key)?.msg || null;
    return null;
  };

  const vitaminRows = [
    { key: '비타민A(mcg)', label: 'A', unit: 'mcg' },
    { key: '비타민B1(mg)', label: 'B1', unit: 'mg' },
    { key: '비타민B2(mg)', label: 'B2', unit: 'mg' },
    { key: '비타민B6(mg)', label: 'B6', unit: 'mg' },
    { key: '나이아신(mg)', label: '나이아신', unit: 'mg' },
    { key: '판토텐산(mg)', label: '판토텐산', unit: 'mg' },
    { key: '비타민B12(mcg)', label: 'B12', unit: 'mcg' },
    { key: '폴산(mcg)', label: '폴산', unit: 'mcg' },
    { key: '비타민D(mcg)', label: 'D', unit: 'mcg' },
    { key: '비타민E(mg)', label: 'E', unit: 'mg' },
    { key: '비타민K(mcg)', label: 'K', unit: 'mcg' },
  ];

  const mineralRows = [
    { key: '마그네슘(mg)', label: 'Mg', unit: 'mg' },
    { key: '나트륨(mg)', label: 'Na', unit: 'mg' },
    { key: '칼륨(mg)', label: 'K', unit: 'mg' },
    { key: '철(mg)', label: 'Fe', unit: 'mg' },
    { key: '구리(mg)', label: 'Cu', unit: 'mg' },
    { key: '아연(mg)', label: 'Zn', unit: 'mg' },
    { key: '망간(mg)', label: 'Mn', unit: 'mg' },
    { key: '셀레늄(mcg)', label: 'Se', unit: 'mcg' },
    { key: '요오드(mcg)', label: 'I', unit: 'mcg' },
  ];

  return (
    <div className="bg-white rounded p-1.5 shadow-sm border">
      <h3 className="font-bold text-[11px] mb-1 text-gray-800">기본 영양 정보</h3>

      {warnings.length > 0 && (
        <div className="mb-1 p-1 bg-red-50 rounded text-[10px] space-y-0">
          {warnings.map((w, i) => (
            <div key={i} className={w.type === 'blue' ? 'text-blue-600 font-bold' : 'text-red-600 font-bold'}>
              {w.msg}
              {w.detail && <span className="font-normal text-gray-600 ml-1">{w.detail}</span>}
            </div>
          ))}
        </div>
      )}

      <table className="w-full">
        <thead>
          <tr className="border-b border-gray-300">
            <th className="text-[9px] text-left py-0">항목</th>
            <th className="text-[9px] text-right py-0">값</th>
            <th className="text-[9px] text-right py-0">DM%</th>
            <th className="text-[9px] text-right py-0">과부족</th>
            <th className="text-[9px] text-left py-0">경고</th>
          </tr>
        </thead>
        <tbody>
          <Row label="총 량" value={fmt(totalGrams)} unit="g" />
          <Row label="하루 섭취량" value={fmt(dailyGrams)} unit="g" />
          <Row label="칼로리" value={fmt(daily['칼로리(Kcal)'])} unit="Kcal" />
          <Row label="수분" value={fmt(waterG)} unit="g"
            dm={dailyGrams > 0 ? `${((waterG / dailyGrams) * 100).toFixed(1)}%` : ''} />
          <Row label="단백질" value={fmt(daily['단백질(g)'])} unit="g"
            dm={dmPct(daily['단백질(g)'] || 0)} sufficiency={getSuff('단백질(g)')} suffRaw={getSuffRaw('단백질(g)')}
            isUpperExceeded={isUE('단백질(g)')} />
          <Row label="지방" value={fmt(daily['지방(g)'])} unit="g"
            dm={dmPct(daily['지방(g)'] || 0)} sufficiency={getSuff('지방(g)')} suffRaw={getSuffRaw('지방(g)')}
            isUpperExceeded={isUE('지방(g)')} />
          <Row label="탄수화물" value={fmt(daily['탄수화물(g)'])} unit="g"
            dm={dmPct(daily['탄수화물(g)'] || 0)} />
          <Row label="칼슘" value={fmt(calcium)} unit="mg"
            dm={dmPct(calcium / 1000)} sufficiency={getSuff('칼슘(mg)')} suffRaw={getSuffRaw('칼슘(mg)')}
            isUpperExceeded={calciumDmRatio > 0.04} />
          <Row label="인" value={fmt(phosphorus)} unit="mg"
            dm={dmPct(phosphorus / 1000)} sufficiency={getSuff('인(mg)')} suffRaw={getSuffRaw('인(mg)')}
            isUpperExceeded={isUE('인(mg)')} />
          <Row label="인:칼슘비" value={phosphorus > 0 ? `1 : ${(calcium / phosphorus).toFixed(2)}` : '-'} />
          <Row label="뼈:살 비율" value={`${bonePct.toFixed(1)}% : ${meatPct.toFixed(1)}%`} />

          <tr><td colSpan={5} className="text-[9px] font-semibold pt-1 text-gray-600">비타민</td></tr>
          {vitaminRows.map(({ key, label, unit }) => (
            <Row key={key} label={label} value={fmt(daily[key])} unit={unit}
              sufficiency={getSuff(key)} suffRaw={getSuffRaw(key)}
              isUpperExceeded={isUE(key)} />
          ))}

          <tr><td colSpan={5} className="text-[9px] font-semibold pt-1 text-gray-600">무기질</td></tr>
          {mineralRows.map(({ key, label, unit }) => (
            <Row key={key} label={label} value={fmt(daily[key])} unit={unit}
              sufficiency={getSuff(key)} suffRaw={getSuffRaw(key)}
              isUpperExceeded={isUE(key)} />
          ))}

          <tr><td colSpan={5} className="text-[9px] font-semibold pt-1 text-gray-600">타우린</td></tr>
          <Row label="타우린" value={fmt(daily['타우린(mg)'])} unit="mg"
            sufficiency={getSuff('타우린(mg)')} suffRaw={getSuffRaw('타우린(mg)')}
            isUpperExceeded={isUE('타우린(mg)')} />
        </tbody>
      </table>
    </div>
  );
}

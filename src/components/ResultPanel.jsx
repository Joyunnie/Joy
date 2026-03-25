import { calcDMPercent } from '../engine/nutrients';

const fmt = (v) => v != null && !isNaN(v) ? v.toFixed(1) : '-';
const fmtPct = (v) => v != null && !isNaN(v) ? `${Math.round(v * 100)}%` : '-';

function Row({ label, value, unit, extra, sufficiency, warning }) {
  return (
    <tr className="border-b border-gray-100">
      <td className="text-xs py-0.5 pr-2">{label}</td>
      <td className="text-xs py-0.5 text-right pr-1">{value}{unit && <span className="text-gray-400 ml-0.5">{unit}</span>}</td>
      <td className="text-xs py-0.5 text-right pr-1 text-gray-500">{extra || ''}</td>
      <td className="text-xs py-0.5 text-right pr-1">{sufficiency || ''}</td>
      <td className="text-xs py-0.5">{warning && <span className={warning.type === 'blue' ? 'text-blue-600 font-bold' : 'text-red-600 font-bold'}>{warning.msg}</span>}</td>
    </tr>
  );
}

export default function ResultPanel({ daily, totals, dailyCalories, sufficiency, warnings, slotStates }) {
  if (!daily) return <div className="bg-white rounded-lg p-3 shadow-sm border"><p className="text-xs text-gray-400">데이터를 입력하세요</p></div>;

  const dailyGrams = daily._dailyGrams || 0;
  const totalGrams = daily._totalGrams || 0;
  const waterG = daily['수분(g)'] || 0;

  const dmPct = (nutrientG) => {
    const v = calcDMPercent(nutrientG, dailyGrams, waterG);
    return v > 0 ? `DM ${v.toFixed(1)}%` : '';
  };

  const getWarning = (key) => warnings.find(w => w.msg.includes(key));
  const getSuff = (key) => sufficiency[key] != null ? fmtPct(sufficiency[key]) : '-';

  // Ca:P ratio
  const calcium = daily['칼슘(mg)'] || 0;
  const phosphorus = daily['인(mg)'] || 0;
  const caPRatio = phosphorus > 0 ? (calcium / phosphorus) : 0;

  // Bone:meat ratio
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
  const boneDenom = rawBone + rmb + meatTotal + organTotal;
  const boneRatio = boneDenom > 0 ? (rawBone + rmb * 0.6) / boneDenom : 0;

  const vitaminRows = [
    { key: '비타민A(mcg)', label: '비타민A', unit: 'mcg' },
    { key: '비타민B1(mg)', label: '비타민B1', unit: 'mg' },
    { key: '비타민B2(mg)', label: '비타민B2', unit: 'mg' },
    { key: '비타민B6(mg)', label: '비타민B6', unit: 'mg' },
    { key: '나이아신(mg)', label: '나이아신', unit: 'mg' },
    { key: '판토텐산(mg)', label: '판토텐산', unit: 'mg' },
    { key: '비타민B12(mcg)', label: '비타민B12', unit: 'mcg' },
    { key: '폴산(mcg)', label: '폴산', unit: 'mcg' },
    { key: '비타민D(mcg)', label: '비타민D', unit: 'mcg' },
    { key: '비타민E(mg)', label: '비타민E', unit: 'mg' },
    { key: '비타민K(mcg)', label: '비타민K', unit: 'mcg' },
  ];

  const mineralRows = [
    { key: '마그네슘(mg)', label: '마그네슘', unit: 'mg' },
    { key: '나트륨(mg)', label: '나트륨', unit: 'mg' },
    { key: '칼륨(mg)', label: '칼륨', unit: 'mg' },
    { key: '철(mg)', label: '철', unit: 'mg' },
    { key: '구리(mg)', label: '구리', unit: 'mg' },
    { key: '아연(mg)', label: '아연', unit: 'mg' },
    { key: '망간(mg)', label: '망간', unit: 'mg' },
    { key: '셀레늄(mcg)', label: '셀레늄', unit: 'mcg' },
    { key: '요오드(mcg)', label: '요오드', unit: 'mcg' },
  ];

  return (
    <div className="bg-white rounded-lg p-3 shadow-sm border">
      <h3 className="font-bold text-sm mb-2 text-gray-800">기본 영양 정보</h3>

      {/* Warning messages */}
      {warnings.length > 0 && (
        <div className="mb-2 p-2 bg-red-50 rounded text-xs space-y-0.5">
          {warnings.map((w, i) => (
            <div key={i} className={w.type === 'blue' ? 'text-blue-600 font-bold' : 'text-red-600 font-bold'}>
              {w.msg}
              {w.detail && <div className="font-normal text-gray-600 ml-2">{w.detail}</div>}
            </div>
          ))}
        </div>
      )}

      <table className="w-full">
        <thead>
          <tr className="border-b border-gray-300">
            <th className="text-xs text-left py-0.5">항목</th>
            <th className="text-xs text-right py-0.5">값</th>
            <th className="text-xs text-right py-0.5">비고</th>
            <th className="text-xs text-right py-0.5">과부족%</th>
            <th className="text-xs text-left py-0.5">경고</th>
          </tr>
        </thead>
        <tbody>
          <Row label="총 량" value={fmt(totalGrams)} unit="g" />
          <Row label="하루 섭취량" value={fmt(dailyGrams)} unit="g" />
          <Row label="칼로리" value={fmt(daily['칼로리(Kcal)'])} unit="Kcal" />
          <Row
            label="수분량"
            value={fmt(waterG)}
            unit="g"
            extra={dailyGrams > 0 ? `${((waterG / dailyGrams) * 100).toFixed(1)}%` : ''}
          />
          <Row
            label="단백질"
            value={fmt(daily['단백질(g)'])}
            unit="g"
            extra={dmPct(daily['단백질(g)'] || 0)}
            sufficiency={getSuff('단백질(g)')}
          />
          <Row
            label="지방"
            value={fmt(daily['지방(g)'])}
            unit="g"
            extra={dmPct(daily['지방(g)'] || 0)}
            sufficiency={getSuff('지방(g)')}
          />
          <Row
            label="탄수화물"
            value={fmt(daily['탄수화물(g)'])}
            unit="g"
            extra={dmPct(daily['탄수화물(g)'] || 0)}
          />
          <Row
            label="칼슘"
            value={fmt(calcium)}
            unit="mg"
            extra={dmPct(calcium / 1000)}
            sufficiency={getSuff('칼슘(mg)')}
          />
          <Row
            label="인"
            value={fmt(phosphorus)}
            unit="mg"
            extra={dmPct(phosphorus / 1000)}
            sufficiency={getSuff('인(mg)')}
          />
          <Row label="인:칼슘비" value={fmt(caPRatio)} />
          <Row label="뼈:살 비율" value={fmt(boneRatio)} />

          {/* Vitamins */}
          <tr><td colSpan={5} className="text-xs font-semibold pt-2 pb-0.5 text-gray-600">비타민</td></tr>
          {vitaminRows.map(({ key, label, unit }) => (
            <Row key={key} label={label} value={fmt(daily[key])} unit={unit} sufficiency={getSuff(key)} />
          ))}

          {/* Minerals */}
          <tr><td colSpan={5} className="text-xs font-semibold pt-2 pb-0.5 text-gray-600">무기질</td></tr>
          {mineralRows.map(({ key, label, unit }) => (
            <Row
              key={key}
              label={label}
              value={fmt(daily[key])}
              unit={unit}
              sufficiency={getSuff(key)}
              warning={key === '셀레늄(mcg)' ? warnings.find(w => w.msg.includes('셀레늄')) : undefined}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

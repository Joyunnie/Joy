import { useState } from 'react';

const fmt = (v) => v != null && !isNaN(v) ? v.toFixed(1) : '-';
const fmtPct = (v) => v != null && !isNaN(v) ? `${Math.round(v * 100)}%` : '-';

function suffLabel(v, isUpperExceeded) {
  if (v == null || isNaN(v)) return '';
  const pct = Math.round(v * 100);
  if (pct === 0) return '';
  if (pct < 100) return ' (부족)';
  if (isUpperExceeded) return ' (과다)';
  return '';
}

function suffColor(v, isUpperExceeded) {
  if (v == null || isNaN(v)) return 'text-gray-400';
  const pct = Math.round(v * 100);
  if (pct === 0) return 'text-gray-400';
  if (pct < 100) return 'text-red-600';
  if (isUpperExceeded) return 'text-red-600';
  return 'text-green-600';
}

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
];

const fattyAcidKeys = [
  { key: '총지방산(mg)', label: '총 지방산', unit: 'mg' },
  { key: '포화지방산(mg)', label: '포화지방산', unit: 'mg' },
  { key: '불포화지방산(mg)', label: '불포화지방산', unit: 'mg' },
  { key: '콜레스테롤(mg)', label: '콜레스테롤', unit: 'mg' },
  { key: 'n-3(mg)', label: 'n-3', unit: 'mg' },
  { key: 'n-6(mg)', label: 'n-6', unit: 'mg' },
  { key: '_n3n6ratio', label: 'n-3:n-6', unit: '', isRatio: true },
  { key: '리놀레산(mg)', label: '리놀레산', unit: 'mg' },
  { key: '알파리놀렌산(mg)', label: '알파리놀렌산', unit: 'mg' },
  { key: 'EPA(mg)', label: 'EPA', unit: 'mg' },
  { key: 'DHA(mg)', label: 'DHA', unit: 'mg' },
  { key: '_epaDha', label: 'EPA+DHA', unit: 'mg', isComputed: true },
  { key: '_epaDhaRatio', label: 'EPA:DHA', unit: '', isRatio: true },
];

function Accordion({ title, defaultOpen = false, children }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="bg-white rounded p-1.5 shadow-sm border">
      <button onClick={() => setOpen(!open)} className="flex items-center w-full text-left">
        <h3 className="font-bold text-[11px] text-gray-800">{title}</h3>
        <span className="text-[9px] text-gray-400 ml-auto">{open ? '▲' : '▼'}</span>
      </button>
      {open && <div className="mt-1">{children}</div>}
    </div>
  );
}

export default function DetailedResults({ daily, sufficiency, slotStates }) {
  if (!daily) return null;

  const upperExceeded = sufficiency._upperExceeded || {};
  const isUE = (key) => !!upperExceeded[key];
  const getSuff = (key) => sufficiency[key] != null ? fmtPct(sufficiency[key]) : '-';
  const getSuffRaw = (key) => sufficiency[key] != null ? sufficiency[key] : null;

  const epa = daily['EPA(mg)'] || 0;
  const dha = daily['DHA(mg)'] || 0;
  const n3 = daily['n-3(mg)'] || 0;
  const n6 = daily['n-6(mg)'] || 0;

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
  let veggieTotal = 0;
  for (let i = 0; i < 3; i++) veggieTotal += getAmt(`veggie_${i}`);
  let otherVegTotal = 0;
  for (let i = 0; i < 3; i++) otherVegTotal += getAmt(`otherVeg_${i}`);
  let directTotal = 0;
  for (let i = 0; i < 7; i++) directTotal += getAmt(`direct_${i}`);

  const organDenom = rawBone + meatTotal + organTotal;
  const organPct = organDenom > 0 ? (organTotal / organDenom) * 100 : 0;
  const meatOnlyPct = organDenom > 0 ? 100 - organPct : 0;
  const pureeTotal = veggieTotal + otherVegTotal + directTotal;
  const pureeDenom = rawBone + rmb + meatTotal + organTotal + pureeTotal;
  const pureePct = pureeDenom > 0 ? (pureeTotal / pureeDenom) * 100 : 0;
  const nonPureePct = pureeDenom > 0 ? 100 - pureePct : 0;

  return (
    <div className="space-y-1">
      <Accordion title="아미노산">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-300">
              <th className="text-[9px] text-left py-0">항목</th>
              <th className="text-[9px] text-right py-0">mg</th>
              <th className="text-[9px] text-right py-0">과부족</th>
              <th className="text-[9px] py-0"></th>
            </tr>
          </thead>
          <tbody>
            {aminoAcidKeys.map(({ key, label }) => {
              const raw = getSuffRaw(key);
              const sLbl = suffLabel(raw, isUE(key));
              return (
                <tr key={key} className="border-b border-gray-100">
                  <td className="text-[10px] py-0">{label}</td>
                  <td className="text-[10px] py-0 text-right">{fmt(daily[key])}</td>
                  <td className={`text-[10px] py-0 text-right ${suffColor(raw, isUE(key))}`} style={{minWidth: '48px'}}>{getSuff(key)}</td>
                  <td className="text-[9px] py-0 text-left pl-0.5 text-red-600" style={{minWidth: '36px'}}>{sLbl || ''}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Accordion>

      {/* 지방산 - always expanded */}
      <div className="bg-white rounded p-1.5 shadow-sm border">
        <h3 className="font-bold text-[11px] text-gray-800">지방산</h3>
        <div className="mt-1">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-300">
                <th className="text-[9px] text-left py-0">항목</th>
                <th className="text-[9px] text-right py-0">값</th>
                <th className="text-[9px] text-right py-0">과부족</th>
                <th className="text-[9px] py-0"></th>
              </tr>
            </thead>
            <tbody>
              {fattyAcidKeys.map(({ key, label, unit, isRatio, isComputed }) => {
                let val, suff, raw;
                if (key === '_n3n6ratio') { val = n6 > 0 ? fmt(n3 / n6) : '-'; suff = '-'; raw = null; }
                else if (key === '_epaDha') { val = fmt(epa + dha); suff = sufficiency['EPA+DHA'] != null ? fmtPct(sufficiency['EPA+DHA']) : '-'; raw = sufficiency['EPA+DHA'] ?? null; }
                else if (key === '_epaDhaRatio') { val = dha > 0 ? fmt(epa / dha) : '-'; suff = '-'; raw = null; }
                else { val = fmt(daily[key]); suff = getSuff(key); raw = getSuffRaw(key); }
                const sLbl = suffLabel(raw, isUE(key));
                return (
                  <tr key={key} className="border-b border-gray-100">
                    <td className="text-[10px] py-0">{label}</td>
                    <td className="text-[10px] py-0 text-right">{val}{unit && !isRatio ? <span className="text-gray-400 ml-0.5">{unit}</span> : ''}</td>
                    <td className={`text-[10px] py-0 text-right ${suffColor(raw, isUE(key))}`} style={{minWidth: '48px'}}>{suff}</td>
                    <td className="text-[9px] py-0 text-left pl-0.5 text-red-600" style={{minWidth: '36px'}}>{sLbl || ''}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <div className="bg-white rounded p-1.5 shadow-sm border">
        <h3 className="font-bold text-[11px] mb-0.5 text-gray-800">비율 정보</h3>
        <div className="space-y-0 text-[10px]">
          <div className="flex justify-between"><span>내장:육류</span><span className="font-semibold">{organPct.toFixed(1)}% : {meatOnlyPct.toFixed(1)}%</span></div>
          <div className="flex justify-between"><span>퓨레:육류</span><span className="font-semibold">{pureePct.toFixed(1)}% : {nonPureePct.toFixed(1)}%</span></div>
        </div>
      </div>
    </div>
  );
}

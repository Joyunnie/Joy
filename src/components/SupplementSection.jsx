import SlotRow from './SlotRow';
import { SLOT_DEFS } from '../data/appConfig';

const sectionGroups = [
  { title: '난류', sections: ['egg'] },
  { title: '비타민', sections: ['vitamin'] },
  { title: '타우린(캡슐)', sections: ['tauCap'] },
  { title: '타우린(mg)', sections: ['tauMg'] },
  { title: '오메가3', sections: ['omega'] },
  { title: '미네랄', sections: ['mineral'] },
  { title: '기타 야채퓨레', sections: ['otherVeg'] },
  { title: '직접 넣는 데이터', sections: ['direct'] },
];

export default function SupplementSection({ slotStates, onSlotUpdate }) {
  return (
    <div className="bg-white rounded p-1.5 shadow-sm border">
      <h3 className="font-bold text-[11px] mb-1 text-gray-800">보조 재료 (선택)</h3>
      {sectionGroups.map(({ title, sections }) => {
        const slots = SLOT_DEFS.filter(d => sections.includes(d.section));
        return (
          <div key={title} className="mb-1">
            <h4 className="text-[10px] font-semibold text-gray-600">{title}</h4>
            {slots.map((def) => {
              const state = slotStates[def.id] || {};
              return (
                <SlotRow key={def.id} slotDef={def} dropdown={state.dropdown} amount={state.amount}
                  onDropdownChange={(v) => onSlotUpdate(def.id, 'dropdown', v)}
                  onAmountChange={(v) => onSlotUpdate(def.id, 'amount', v)}
                />
              );
            })}
          </div>
        );
      })}
    </div>
  );
}

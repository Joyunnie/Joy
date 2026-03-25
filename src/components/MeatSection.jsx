import SlotRow from './SlotRow';
import { SLOT_DEFS } from '../data/appConfig';

const calciumSlots = SLOT_DEFS.filter(d => d.section === 'calcium');
const meatSlots = SLOT_DEFS.filter(d => d.section === 'meat');
const organSlots = SLOT_DEFS.filter(d => d.section === 'organ');
const waterSlots = SLOT_DEFS.filter(d => d.section === 'water');

export default function MeatSection({ slotStates, onSlotUpdate }) {
  const renderGroup = (title, slots) => (
    <div className="mb-1">
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

  return (
    <div className="bg-white rounded p-1.5 shadow-sm border">
      <h3 className="font-bold text-[11px] mb-1 text-gray-800">육류 (필수)</h3>
      {renderGroup('칼슘류', calciumSlots)}
      {renderGroup('고기류', meatSlots)}
      {renderGroup('내장류', organSlots)}
      {renderGroup('물', waterSlots)}
    </div>
  );
}

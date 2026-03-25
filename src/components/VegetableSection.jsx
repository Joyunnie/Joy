import SlotRow from './SlotRow';
import { SLOT_DEFS } from '../data/appConfig';

const veggieSlots = SLOT_DEFS.filter(d => d.section === 'veggie');

export default function VegetableSection({ slotStates, onSlotUpdate }) {
  return (
    <div className="bg-white rounded p-1.5 shadow-sm border">
      <h3 className="font-bold text-[11px] mb-1 text-gray-800">야채 퓨레 (선택)</h3>
      {veggieSlots.map((def) => {
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
}

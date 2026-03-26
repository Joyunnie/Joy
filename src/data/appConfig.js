import rawConfig from '../../app_config.json';

export const nrc = rawConfig.nrc;
export const presets = rawConfig.presets;
export const dropdownMapping = rawConfig.dropdown_mapping;

// Complete cell-to-slot mapping for preset loading
export const CELL_TO_SLOT = {
  // Calcium: old 5 cells → grouped import (calcium_0-2, merged '칼슘류')
  // Preset dropdown values need source category for merged index conversion
  G4: { slotId: 'calcium_0', type: 'dropdown', source: '식품A' },
  G5: { slotId: 'calcium_1', type: 'dropdown', source: '식품B' },
  G6: { slotId: 'calcium_2', type: 'dropdown', source: '식품C' },
  G7: { group: 'calcium', type: 'dropdown', source: '식품AA' },
  G8: { group: 'calcium', type: 'dropdown', source: '식품D' },
  H4: { slotId: 'calcium_0', type: 'value' },
  H5: { slotId: 'calcium_1', type: 'value' },
  H6: { slotId: 'calcium_2', type: 'value' },
  H7: { group: 'calcium', type: 'value' },
  H8: { group: 'calcium', type: 'value' },

  // Meat (F10-F16 dropdowns, H10-H16 values) - reduced to 7
  ...Object.fromEntries(
    Array.from({ length: 7 }, (_, i) => [`F${10 + i}`, { slotId: `meat_${i}`, type: 'dropdown' }])
  ),
  ...Object.fromEntries(
    Array.from({ length: 7 }, (_, i) => [`H${10 + i}`, { slotId: `meat_${i}`, type: 'value' }])
  ),
  // F17-F18 overflow (old meat_7, meat_8) - kept for preset compat
  F17: { group: 'meat', type: 'dropdown' },
  F18: { group: 'meat', type: 'dropdown' },
  H17: { group: 'meat', type: 'value' },
  H18: { group: 'meat', type: 'value' },

  // Organs (F20-F24 dropdowns, H20-H24 values)
  ...Object.fromEntries(
    Array.from({ length: 5 }, (_, i) => [`F${20 + i}`, { slotId: `organ_${i}`, type: 'dropdown' }])
  ),
  ...Object.fromEntries(
    Array.from({ length: 5 }, (_, i) => [`H${20 + i}`, { slotId: `organ_${i}`, type: 'value' }])
  ),

  // Water
  F25: { slotId: 'water_0', type: 'dropdown' },
  H25: { slotId: 'water_0', type: 'value' },

  // Vegetables (F28-F30 dropdowns, H28-H30 values)
  ...Object.fromEntries(
    Array.from({ length: 3 }, (_, i) => [`F${28 + i}`, { slotId: `veggie_${i}`, type: 'dropdown' }])
  ),
  ...Object.fromEntries(
    Array.from({ length: 3 }, (_, i) => [`H${28 + i}`, { slotId: `veggie_${i}`, type: 'value' }])
  ),

  // Eggs (K4-K5, L4-L5)
  K4: { slotId: 'egg_0', type: 'dropdown' },
  K5: { slotId: 'egg_1', type: 'dropdown' },
  L4: { slotId: 'egg_0', type: 'value' },
  L5: { slotId: 'egg_1', type: 'value' },

  // Vitamin: old 6 cells → vitamin_0-5 (merged '비타민')
  K7: { slotId: 'vitamin_0', type: 'dropdown', source: '식품G' },
  K8: { slotId: 'vitamin_1', type: 'dropdown', source: '식품G' },
  K10: { slotId: 'vitamin_2', type: 'dropdown', source: '식품H' },
  K11: { slotId: 'vitamin_3', type: 'dropdown', source: '식품HH' },
  K13: { slotId: 'vitamin_4', type: 'dropdown', source: '식품I' },
  K14: { slotId: 'vitamin_5', type: 'dropdown', source: '식품I' },
  L7: { slotId: 'vitamin_0', type: 'value' },
  L8: { slotId: 'vitamin_1', type: 'value' },
  L10: { slotId: 'vitamin_2', type: 'value' },
  L11: { slotId: 'vitamin_3', type: 'value' },
  L13: { slotId: 'vitamin_4', type: 'value' },
  L14: { slotId: 'vitamin_5', type: 'value' },

  // Taurine capsule (K16, L16)
  K16: { slotId: 'tauCap_0', type: 'dropdown' },
  L16: { slotId: 'tauCap_0', type: 'value' },

  // Taurine mg (K17, L17)
  K17: { slotId: 'tauMg_0', type: 'dropdown' },
  L17: { slotId: 'tauMg_0', type: 'value' },

  // Omega3 (K19-K20, L19-L20)
  K19: { slotId: 'omega_0', type: 'dropdown' },
  K20: { slotId: 'omega_1', type: 'dropdown' },
  L19: { slotId: 'omega_0', type: 'value' },
  L20: { slotId: 'omega_1', type: 'value' },

  // Mineral (K22-K25 kept for legacy preset compat, no active slots)
  // Old fiber slots removed - mineral uses its own section without cell mapping

  // Other veggies (K28-K30, L28-L30)
  ...Object.fromEntries(
    Array.from({ length: 3 }, (_, i) => [`K${28 + i}`, { slotId: `otherVeg_${i}`, type: 'dropdown' }])
  ),
  ...Object.fromEntries(
    Array.from({ length: 3 }, (_, i) => [`L${28 + i}`, { slotId: `otherVeg_${i}`, type: 'value' }])
  ),

  // Direct data (K36-K38, L36-L38)
  ...Object.fromEntries(
    Array.from({ length: 3 }, (_, i) => [`K${36 + i}`, { slotId: `direct_${i}`, type: 'dropdown' }])
  ),
  ...Object.fromEntries(
    Array.from({ length: 3 }, (_, i) => [`L${36 + i}`, { slotId: `direct_${i}`, type: 'value' }])
  ),

  // Special: recipe days
  C13: { field: 'recipeDays', type: 'basicInfo' },
};

// Slot definitions: each slot has an ID, category key, section, label, unit
export const SLOT_DEFS = [
  // Calcium (3 unified slots, merged category '칼슘류')
  ...Array.from({ length: 3 }, (_, i) => ({
    id: `calcium_${i}`, category: '칼슘류', section: 'calcium', label: `칼슘류${i + 1}`, unit: 'g'
  })),
  // Meat (7 slots, all 식품F)
  ...Array.from({ length: 7 }, (_, i) => ({
    id: `meat_${i}`, category: '식품F', section: 'meat', label: `고기류${i + 1}`, unit: 'g'
  })),
  // Organs (5 slots, all 식품FF)
  ...Array.from({ length: 5 }, (_, i) => ({
    id: `organ_${i}`, category: '식품FF', section: 'organ', label: `내장류${i + 1}`, unit: 'g'
  })),
  // Water (special)
  { id: 'water_0', category: 'water', section: 'water', label: '물', unit: 'g' },
  // Vegetables (3 slots, all 식품P)
  ...Array.from({ length: 3 }, (_, i) => ({
    id: `veggie_${i}`, category: '식품P', section: 'veggie', label: `채소류${i + 1}`, unit: 'g'
  })),
  // Eggs
  { id: 'egg_0', category: '식품L', section: 'egg', label: '난류1', unit: 'g' },
  { id: 'egg_1', category: '식품L', section: 'egg', label: '난류2', unit: 'g' },
  // Vitamin (6 unified slots, merged category '비타민')
  ...Array.from({ length: 6 }, (_, i) => ({
    id: `vitamin_${i}`, category: '비타민', section: 'vitamin', label: `비타민${i + 1}`, unit: ''
  })),
  // Taurine
  { id: 'tauCap_0', category: '식품J', section: 'tauCap', label: '타우린(캡슐)', unit: '캡슐' },
  { id: 'tauMg_0', category: '식품JJ', section: 'tauMg', label: '타우린(mg)', unit: 'mg' },
  // Omega3
  { id: 'omega_0', category: '식품K', section: 'omega', label: '오메가3-1', unit: '겔' },
  { id: 'omega_1', category: '식품K', section: 'omega', label: '오메가3-2', unit: '겔' },
  // Mineral (7 slots)
  ...Array.from({ length: 7 }, (_, i) => ({
    id: `mineral_${i}`, category: '미네랄', section: 'mineral', label: `미네랄${i + 1}`, unit: ''
  })),
  // Other veggies
  ...Array.from({ length: 3 }, (_, i) => ({
    id: `otherVeg_${i}`, category: '식품Q', section: 'otherVeg', label: `기타야채${i + 1}`, unit: 'g'
  })),
  // Direct data (3 slots)
  ...Array.from({ length: 3 }, (_, i) => ({
    id: `direct_${i}`, category: '식품R', section: 'direct', label: `직접데이터${i + 1}`, unit: 'g'
  })),
];

// Merged category source → offset for converting old preset dropdown indices
const MERGED_SOURCE_OFFSETS = {
  '식품A': 0, '식품AA': 1000, '식품B': 2000, '식품C': 3000, '식품D': 4000,
  '식품G': 0, '식품H': 1000, '식품HH': 2000, '식품I': 3000,
};

// Helper: load preset into state
export function loadPreset(presetName) {
  const preset = presets[presetName];
  if (!preset) return null;

  const slots = {};
  const values = {};

  // Process dropdowns
  for (const [cell, idx] of Object.entries(preset.dropdowns)) {
    const mapping = CELL_TO_SLOT[cell];
    if (!mapping || mapping.type !== 'dropdown') continue;
    if (!mapping.slotId) continue; // overflow slots (group only) are skipped
    let mergedIdx = idx;
    if (mapping.source && MERGED_SOURCE_OFFSETS[mapping.source] != null) {
      mergedIdx = MERGED_SOURCE_OFFSETS[mapping.source] + idx;
    }
    slots[mapping.slotId] = mergedIdx;
  }

  // Process values
  let recipeDays = null;
  for (const [cell, val] of Object.entries(preset.values)) {
    const mapping = CELL_TO_SLOT[cell];
    if (!mapping) continue;
    if (mapping.type === 'basicInfo') {
      recipeDays = val;
    } else if (mapping.type === 'value' && mapping.slotId) {
      values[mapping.slotId] = val;
    }
  }

  return { slots, values, recipeDays };
}

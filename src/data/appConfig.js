import rawConfig from '../../app_config.json';

export const nrc = rawConfig.nrc;
export const presets = rawConfig.presets;
export const dropdownMapping = rawConfig.dropdown_mapping;

// Complete cell-to-slot mapping for preset loading
export const CELL_TO_SLOT = {
  // Calcium (G column dropdowns, H column values)
  G4: { slotId: 'calcium_0', type: 'dropdown' },
  G5: { slotId: 'calcium_1', type: 'dropdown' },
  G6: { slotId: 'calcium_2', type: 'dropdown' },
  G7: { slotId: 'calcium_3', type: 'dropdown' },
  G8: { slotId: 'calcium_4', type: 'dropdown' },
  H4: { slotId: 'calcium_0', type: 'value' },
  H5: { slotId: 'calcium_1', type: 'value' },
  H6: { slotId: 'calcium_2', type: 'value' },
  H7: { slotId: 'calcium_3', type: 'value' },
  H8: { slotId: 'calcium_4', type: 'value' },

  // Meat (F10-F18 dropdowns, H10-H18 values)
  ...Object.fromEntries(
    Array.from({ length: 9 }, (_, i) => [`F${10 + i}`, { slotId: `meat_${i}`, type: 'dropdown' }])
  ),
  ...Object.fromEntries(
    Array.from({ length: 9 }, (_, i) => [`H${10 + i}`, { slotId: `meat_${i}`, type: 'value' }])
  ),

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

  // Vegetables (F28-F40 dropdowns, H28-H40 values)
  ...Object.fromEntries(
    Array.from({ length: 13 }, (_, i) => [`F${28 + i}`, { slotId: `veggie_${i}`, type: 'dropdown' }])
  ),
  ...Object.fromEntries(
    Array.from({ length: 13 }, (_, i) => [`H${28 + i}`, { slotId: `veggie_${i}`, type: 'value' }])
  ),

  // Eggs (K4-K5, L4-L5)
  K4: { slotId: 'egg_0', type: 'dropdown' },
  K5: { slotId: 'egg_1', type: 'dropdown' },
  L4: { slotId: 'egg_0', type: 'value' },
  L5: { slotId: 'egg_1', type: 'value' },

  // Vitamin B (K7-K8, L7-L8)
  K7: { slotId: 'vitB_0', type: 'dropdown' },
  K8: { slotId: 'vitB_1', type: 'dropdown' },
  L7: { slotId: 'vitB_0', type: 'value' },
  L8: { slotId: 'vitB_1', type: 'value' },

  // Yeast tsp (K10, L10)
  K10: { slotId: 'yeastTsp_0', type: 'dropdown' },
  L10: { slotId: 'yeastTsp_0', type: 'value' },

  // Yeast g (K11, L11)
  K11: { slotId: 'yeastG_0', type: 'dropdown' },
  L11: { slotId: 'yeastG_0', type: 'value' },

  // Vitamin E (K13-K14, L13-L14)
  K13: { slotId: 'vitE_0', type: 'dropdown' },
  K14: { slotId: 'vitE_1', type: 'dropdown' },
  L13: { slotId: 'vitE_0', type: 'value' },
  L14: { slotId: 'vitE_1', type: 'value' },

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

  // Fiber tsp (K22-K23, L22-L23)
  K22: { slotId: 'fiberTsp_0', type: 'dropdown' },
  K23: { slotId: 'fiberTsp_1', type: 'dropdown' },
  L22: { slotId: 'fiberTsp_0', type: 'value' },
  L23: { slotId: 'fiberTsp_1', type: 'value' },

  // Fiber g (K24-K25, L24-L25)
  K24: { slotId: 'fiberG_0', type: 'dropdown' },
  K25: { slotId: 'fiberG_1', type: 'dropdown' },
  L24: { slotId: 'fiberG_0', type: 'value' },
  L25: { slotId: 'fiberG_1', type: 'value' },

  // Other veggies (K28-K34, L28-L34)
  ...Object.fromEntries(
    Array.from({ length: 7 }, (_, i) => [`K${28 + i}`, { slotId: `otherVeg_${i}`, type: 'dropdown' }])
  ),
  ...Object.fromEntries(
    Array.from({ length: 7 }, (_, i) => [`L${28 + i}`, { slotId: `otherVeg_${i}`, type: 'value' }])
  ),

  // Direct data (K36-K40, L36-L40)
  ...Object.fromEntries(
    Array.from({ length: 5 }, (_, i) => [`K${36 + i}`, { slotId: `direct_${i}`, type: 'dropdown' }])
  ),
  ...Object.fromEntries(
    Array.from({ length: 5 }, (_, i) => [`L${36 + i}`, { slotId: `direct_${i}`, type: 'value' }])
  ),

  // Special: recipe days
  C13: { field: 'recipeDays', type: 'basicInfo' },
};

// Slot definitions: each slot has an ID, category key, section, label, unit
export const SLOT_DEFS = [
  // Calcium
  { id: 'calcium_0', category: '식품A', section: 'calcium', label: '생뼈류', unit: 'g' },
  { id: 'calcium_1', category: '식품B', section: 'calcium', label: '본밀류', unit: 'g' },
  { id: 'calcium_2', category: '식품C', section: 'calcium', label: '달걀껍질', unit: 'g' },
  { id: 'calcium_3', category: '식품AA', section: 'calcium', label: 'RMB', unit: 'g' },
  { id: 'calcium_4', category: '식품D', section: 'calcium', label: '기타칼슘', unit: 'g' },
  // Meat (9 slots, all 식품F)
  ...Array.from({ length: 9 }, (_, i) => ({
    id: `meat_${i}`, category: '식품F', section: 'meat', label: `고기류${i + 1}`, unit: 'g'
  })),
  // Organs (5 slots, all 식품FF)
  ...Array.from({ length: 5 }, (_, i) => ({
    id: `organ_${i}`, category: '식품FF', section: 'organ', label: `내장류${i + 1}`, unit: 'g'
  })),
  // Water (special)
  { id: 'water_0', category: 'water', section: 'water', label: '물', unit: 'g' },
  // Vegetables (13 slots, all 식품P)
  ...Array.from({ length: 13 }, (_, i) => ({
    id: `veggie_${i}`, category: '식품P', section: 'veggie', label: `채소류${i + 1}`, unit: 'g'
  })),
  // Eggs
  { id: 'egg_0', category: '식품L', section: 'egg', label: '난류1', unit: 'g' },
  { id: 'egg_1', category: '식품L', section: 'egg', label: '난류2', unit: 'g' },
  // Vitamin B
  { id: 'vitB_0', category: '식품G', section: 'vitB', label: '비타민B-1', unit: '캡슐' },
  { id: 'vitB_1', category: '식품G', section: 'vitB', label: '비타민B-2', unit: '캡슐' },
  // Yeast
  { id: 'yeastTsp_0', category: '식품H', section: 'yeastTsp', label: '효모(스푼)', unit: 'tsp' },
  { id: 'yeastG_0', category: '식품HH', section: 'yeastG', label: '효모(g)', unit: 'g' },
  // Vitamin E
  { id: 'vitE_0', category: '식품I', section: 'vitE', label: '비타민E-1', unit: '캡슐' },
  { id: 'vitE_1', category: '식품I', section: 'vitE', label: '비타민E-2', unit: '캡슐' },
  // Taurine
  { id: 'tauCap_0', category: '식품J', section: 'tauCap', label: '타우린(캡슐)', unit: '캡슐' },
  { id: 'tauMg_0', category: '식품JJ', section: 'tauMg', label: '타우린(mg)', unit: 'mg' },
  // Omega3
  { id: 'omega_0', category: '식품K', section: 'omega', label: '오메가3-1', unit: '겔' },
  { id: 'omega_1', category: '식품K', section: 'omega', label: '오메가3-2', unit: '겔' },
  // Fiber tsp
  { id: 'fiberTsp_0', category: '식품M', section: 'fiberTsp', label: '식이섬유(tsp)1', unit: 'tsp' },
  { id: 'fiberTsp_1', category: '식품M', section: 'fiberTsp', label: '식이섬유(tsp)2', unit: 'tsp' },
  // Fiber g
  { id: 'fiberG_0', category: '식품MM', section: 'fiberG', label: '식이섬유(g)1', unit: 'g' },
  { id: 'fiberG_1', category: '식품MM', section: 'fiberG', label: '식이섬유(g)2', unit: 'g' },
  // Other veggies
  ...Array.from({ length: 7 }, (_, i) => ({
    id: `otherVeg_${i}`, category: '식품Q', section: 'otherVeg', label: `기타야채${i + 1}`, unit: 'g'
  })),
  // Direct data
  ...Array.from({ length: 5 }, (_, i) => ({
    id: `direct_${i}`, category: '식품R', section: 'direct', label: `직접데이터${i + 1}`, unit: 'g'
  })),
];

// Helper: load preset into state
export function loadPreset(presetName) {
  const preset = presets[presetName];
  if (!preset) return null;

  const slots = {};
  const values = {};

  // Process dropdowns
  for (const [cell, idx] of Object.entries(preset.dropdowns)) {
    const mapping = CELL_TO_SLOT[cell];
    if (mapping && mapping.type === 'dropdown') {
      slots[mapping.slotId] = idx;
    }
  }

  // Process values
  let recipeDays = null;
  for (const [cell, val] of Object.entries(preset.values)) {
    const mapping = CELL_TO_SLOT[cell];
    if (!mapping) continue;
    if (mapping.type === 'basicInfo') {
      recipeDays = val;
    } else if (mapping.type === 'value') {
      values[mapping.slotId] = val;
    }
  }

  return { slots, values, recipeDays };
}

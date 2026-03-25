import { useState, useMemo, useCallback } from 'react';
import BasicInfo from './components/BasicInfo';
import MeatSection from './components/MeatSection';
import VegetableSection from './components/VegetableSection';
import SupplementSection from './components/SupplementSection';
import Omega3Register from './components/Omega3Register';
import NutrientAdjust from './components/NutrientAdjust';
import ResultPanel from './components/ResultPanel';
import DetailedResults from './components/DetailedResults';
import RecipeManager from './components/RecipeManager';
import CustomIngredient from './components/CustomIngredient';
import { calcCalories } from './engine/calories';
import { calcTotalNutrients, calcDailyNutrients, calcAllSufficiency } from './engine/nutrients';
import { generateWarnings } from './engine/warnings';
import { loadPreset } from './data/appConfig';

const initialBasicInfo = {
  weight: 4,
  calorieType: 2,
  expectedWeight: 4,
  recipeDays: 60,
};

const initialOmega3 = {
  calories: '', fat: '', epa: '', dha: '', otherOmega3: '', vitE: '',
};

const initialNutrientAdjust = {
  protein: '', fat: '', calcium: '', phosphorus: '', sodium: '',
};

export default function App() {
  const [basicInfo, setBasicInfo] = useState(initialBasicInfo);
  const [slotStates, setSlotStates] = useState({});
  const [omega3Custom, setOmega3Custom] = useState(initialOmega3);
  const [nutrientAdjust, setNutrientAdjust] = useState(initialNutrientAdjust);
  const [refreshKey, setRefreshKey] = useState(0);

  const dailyCalories = useMemo(() =>
    calcCalories(basicInfo.calorieType, basicInfo.weight, basicInfo.expectedWeight),
    [basicInfo.calorieType, basicInfo.weight, basicInfo.expectedWeight]
  );

  const isKitten = basicInfo.calorieType === 5 || basicInfo.calorieType === 6;

  const totals = useMemo(() =>
    calcTotalNutrients(slotStates, omega3Custom),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [slotStates, omega3Custom, refreshKey]
  );

  const daily = useMemo(() =>
    calcDailyNutrients(totals, basicInfo.recipeDays),
    [totals, basicInfo.recipeDays]
  );

  const sufficiency = useMemo(() =>
    calcAllSufficiency(daily, dailyCalories, isKitten),
    [daily, dailyCalories, isKitten]
  );

  const warnings = useMemo(() =>
    generateWarnings(daily, dailyCalories, isKitten, slotStates, nutrientAdjust),
    [daily, dailyCalories, isKitten, slotStates, nutrientAdjust]
  );

  const handleBasicInfoUpdate = useCallback((updates) => {
    setBasicInfo(prev => ({ ...prev, ...updates }));
  }, []);

  const handleSlotUpdate = useCallback((slotId, field, value) => {
    setSlotStates(prev => ({
      ...prev,
      [slotId]: { ...prev[slotId], [field]: value },
    }));
  }, []);

  const handleOmega3Update = useCallback((updates) => {
    setOmega3Custom(prev => ({ ...prev, ...updates }));
  }, []);

  const handleNutrientAdjustUpdate = useCallback((updates) => {
    setNutrientAdjust(prev => ({ ...prev, ...updates }));
  }, []);

  const handleLoadPreset = useCallback((presetName) => {
    const preset = loadPreset(presetName);
    if (!preset) return;
    const newSlots = {};
    for (const [slotId, dropdownVal] of Object.entries(preset.slots)) {
      newSlots[slotId] = { ...newSlots[slotId], dropdown: dropdownVal };
    }
    for (const [slotId, amountVal] of Object.entries(preset.values)) {
      newSlots[slotId] = { ...newSlots[slotId], amount: amountVal };
    }
    if (newSlots.water_0?.amount) {
      newSlots.water_0 = { ...newSlots.water_0, dropdown: 2 };
    }
    setSlotStates(newSlots);
    if (preset.recipeDays != null) {
      setBasicInfo(prev => ({ ...prev, recipeDays: preset.recipeDays }));
    }
  }, []);

  const handleReset = useCallback(() => {
    setSlotStates({});
  }, []);

  const handleLoadRecipe = useCallback((recipe) => {
    setBasicInfo(recipe.basicInfo || initialBasicInfo);
    setSlotStates(recipe.slotStates || {});
    setOmega3Custom(recipe.omega3Custom || initialOmega3);
    setNutrientAdjust(recipe.nutrientAdjust || initialNutrientAdjust);
  }, []);

  const handleCustomFoodUpdate = useCallback(() => {
    setRefreshKey(k => k + 1);
  }, []);

  return (
    <div className="min-h-screen bg-gray-100">
      <header className="bg-amber-600 text-white py-1 px-3 shadow-md">
        <h1 className="text-sm font-bold">고양이 생식 레시피 계산기</h1>
      </header>

      <div className="p-1">
        <div className="flex gap-1 mb-1 flex-wrap items-center">
          <button onClick={() => handleLoadPreset('피어슨')}
            className="text-[10px] px-2 py-0.5 bg-green-600 text-white rounded hover:bg-green-700 font-semibold">피어슨</button>
          <button onClick={() => handleLoadPreset('미쉘')}
            className="text-[10px] px-2 py-0.5 bg-blue-600 text-white rounded hover:bg-blue-700 font-semibold">살편네</button>
          <button onClick={handleReset}
            className="text-[10px] px-2 py-0.5 bg-gray-500 text-white rounded hover:bg-gray-600 font-semibold">초기화</button>
        </div>

        <div className="flex gap-1 items-start">
          {/* Left column */}
          <div className="w-72 shrink-0 space-y-1">
            <BasicInfo basicInfo={basicInfo} dailyCalories={dailyCalories} onUpdate={handleBasicInfoUpdate} />
            <MeatSection slotStates={slotStates} onSlotUpdate={handleSlotUpdate} />
            <VegetableSection slotStates={slotStates} onSlotUpdate={handleSlotUpdate} />
            <Omega3Register values={omega3Custom} onUpdate={handleOmega3Update}
              onReset={() => setOmega3Custom(initialOmega3)} />
            <NutrientAdjust values={nutrientAdjust} onUpdate={handleNutrientAdjustUpdate}
              onReset={() => setNutrientAdjust(initialNutrientAdjust)} />
            <RecipeManager basicInfo={basicInfo} slotStates={slotStates}
              omega3Custom={omega3Custom} nutrientAdjust={nutrientAdjust}
              onLoadRecipe={handleLoadRecipe} />
            <CustomIngredient onUpdate={handleCustomFoodUpdate} />
          </div>

          {/* Center column */}
          <div className="w-72 shrink-0">
            <SupplementSection slotStates={slotStates} onSlotUpdate={handleSlotUpdate} />
          </div>

          {/* Right column */}
          <div className="flex-1 min-w-72 space-y-1">
            <ResultPanel daily={daily} totals={totals} dailyCalories={dailyCalories}
              sufficiency={sufficiency} warnings={warnings} slotStates={slotStates} />
            <DetailedResults daily={daily} sufficiency={sufficiency} slotStates={slotStates} />
          </div>
        </div>
      </div>
    </div>
  );
}

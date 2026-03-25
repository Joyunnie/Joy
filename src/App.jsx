import { useState, useMemo, useCallback, useEffect, useRef } from 'react';
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
import NutrientRecommendation from './components/NutrientRecommendation';
import GistSync from './components/GistSync';
import Inventory from './components/Inventory';
import { calcCalories } from './engine/calories';
import { calcTotalNutrients, calcDailyNutrients, calcAllSufficiency } from './engine/nutrients';
import { generateWarnings } from './engine/warnings';

const initialBasicInfo = {
  weight: 4,
  calorieType: 2,
  expectedWeight: 4,
  recipeDays: 60,
  useCustomCalories: false,
  customCalories: '',
};

const initialOmega3 = {
  calories: '', fat: '', epa: '', dha: '', otherOmega3: '', vitE: '',
};

const OMEGA3_STORAGE_KEY = 'catfood_omega3_custom';

function loadOmega3() {
  try {
    const saved = JSON.parse(localStorage.getItem(OMEGA3_STORAGE_KEY));
    if (saved) return saved;
  } catch {}
  return initialOmega3;
}

const initialNutrientAdjust = {
  protein: '', fat: '', calcium: '', phosphorus: '', sodium: '',
};

export default function App() {
  const [basicInfo, setBasicInfo] = useState(initialBasicInfo);
  const [slotStates, setSlotStates] = useState({});
  const [omega3Custom, setOmega3Custom] = useState(loadOmega3);
  const [nutrientAdjust, setNutrientAdjust] = useState(initialNutrientAdjust);
  const [refreshKey, setRefreshKey] = useState(0);
  const resultRef = useRef(null);

  // Persist omega3 to localStorage
  useEffect(() => {
    localStorage.setItem(OMEGA3_STORAGE_KEY, JSON.stringify(omega3Custom));
  }, [omega3Custom]);

  const formulaCalories = useMemo(() =>
    calcCalories(basicInfo.calorieType, basicInfo.weight, basicInfo.expectedWeight),
    [basicInfo.calorieType, basicInfo.weight, basicInfo.expectedWeight]
  );

  const dailyCalories = basicInfo.useCustomCalories && basicInfo.customCalories > 0
    ? Number(basicInfo.customCalories)
    : formulaCalories;

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

  const handleReset = useCallback(() => {
    setSlotStates({});
  }, []);

  const handleOmega3Reset = useCallback(() => {
    setOmega3Custom(initialOmega3);
    localStorage.removeItem(OMEGA3_STORAGE_KEY);
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

  const handleSyncComplete = useCallback(() => {
    // Reload omega3 from localStorage after sync
    setOmega3Custom(loadOmega3());
    setRefreshKey(k => k + 1);
  }, []);

  return (
    <div className="min-h-screen bg-gray-100">
      <header className="bg-amber-600 text-white py-1 px-3 shadow-md">
        <h1 className="text-sm font-bold">고양이 생식 레시피 계산기</h1>
      </header>

      <div className="max-w-[1400px] mx-auto p-1">
        <div className="flex gap-1 mb-1 flex-wrap items-center">
          <button onClick={handleReset}
            className="text-[10px] px-2 py-0.5 bg-gray-500 text-white rounded hover:bg-gray-600 font-semibold">레시피 초기화</button>
        </div>

        <div className="flex gap-1 items-start">
          {/* Left column — 25% */}
          <div className="w-1/4 min-w-[260px] max-w-[320px] shrink-0 space-y-1">
            <BasicInfo basicInfo={basicInfo} dailyCalories={dailyCalories} onUpdate={handleBasicInfoUpdate} />
            <MeatSection slotStates={slotStates} onSlotUpdate={handleSlotUpdate} />
            <VegetableSection slotStates={slotStates} onSlotUpdate={handleSlotUpdate} />
            <Omega3Register values={omega3Custom} onUpdate={handleOmega3Update}
              onReset={handleOmega3Reset} />
            <NutrientAdjust values={nutrientAdjust} onUpdate={handleNutrientAdjustUpdate}
              onReset={() => setNutrientAdjust(initialNutrientAdjust)} />
          </div>

          {/* Center column — 35% */}
          <div className="w-[35%] min-w-[280px] max-w-[420px] shrink-0 space-y-1">
            <GistSync onSyncComplete={handleSyncComplete} />
            <CustomIngredient onUpdate={handleCustomFoodUpdate} />
            <RecipeManager basicInfo={basicInfo} slotStates={slotStates}
              omega3Custom={omega3Custom} nutrientAdjust={nutrientAdjust}
              onLoadRecipe={handleLoadRecipe} resultRef={resultRef} />
            <Inventory onUpdate={handleCustomFoodUpdate} />
            <SupplementSection slotStates={slotStates} onSlotUpdate={handleSlotUpdate} />
          </div>

          {/* Right column — 40% */}
          <div className="w-[40%] min-w-[300px] max-w-[520px] space-y-1" ref={resultRef}>
            <ResultPanel daily={daily} totals={totals} dailyCalories={dailyCalories}
              sufficiency={sufficiency} warnings={warnings} slotStates={slotStates} />
            <DetailedResults daily={daily} sufficiency={sufficiency} slotStates={slotStates} />
            <NutrientRecommendation sufficiency={sufficiency} daily={daily}
              dailyCalories={dailyCalories} isKitten={isKitten} recipeDays={basicInfo.recipeDays} totals={totals} />

            {/* Reference info */}
            <div className="text-right text-xs text-gray-500 leading-relaxed mt-2 pr-1">
              <p className="font-semibold text-gray-600 mb-0.5">참고 정보</p>
              <p><span className="font-semibold">t, T 표기:</span> t = 티스푼, T = 테이블스푼</p>
              <p className="text-[10px]">대부분의 t는 직접 계량한 것, T는 라벨상의 무게</p>
              <p className="text-[10px]">ex) 솔가 맥주효모(15g,T) → 라벨상 1T=15g, 사용량 "1" 입력 시 15g</p>
              <p className="text-[10px]">ex) 칼 영양효모(2g,t) → 직접 계량 1t=2g, 사용량 "1" 입력 시 2g</p>
              <p className="font-semibold text-gray-600 mt-1 mb-0.5">뼈비율 참고</p>
              <p className="text-[10px]">닭: 약 15~20% · 메추리: 약 20~25% · 오리: 약 25~30%</p>
              <p className="text-[10px]">토끼: 메추리 뼈로 10~20% (추후 토끼뼈 추가 예정)</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

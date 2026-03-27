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
        {/* Mobile: single column with ordered sections / PC: 3-column flex */}
        <div className="flex flex-col md:flex-row gap-1 md:items-start md:justify-center" ref={resultRef}>
          {/* Left column — PC: 25% / Mobile: full width, split into ordered sections */}
          <div className="w-full md:w-1/4 md:min-w-[260px] md:max-w-[320px] md:shrink-0 space-y-1 order-2 md:order-none mobile-col-left contents md:block">
            <div className="order-2 md:order-none"><BasicInfo basicInfo={basicInfo} dailyCalories={dailyCalories} onUpdate={handleBasicInfoUpdate} onReset={handleReset} /></div>
            <div className="order-3 md:order-none"><MeatSection slotStates={slotStates} onSlotUpdate={handleSlotUpdate} /></div>
            <div className="order-4 md:order-none"><VegetableSection slotStates={slotStates} onSlotUpdate={handleSlotUpdate} /></div>
            <div className="order-10 md:order-none"><Omega3Register values={omega3Custom} onUpdate={handleOmega3Update}
              onReset={handleOmega3Reset} /></div>
            <div className="order-10 md:order-none"><NutrientAdjust values={nutrientAdjust} onUpdate={handleNutrientAdjustUpdate}
              onReset={() => setNutrientAdjust(initialNutrientAdjust)} /></div>
          </div>

          {/* Center column — PC: 35% / Mobile: full width, split into ordered sections */}
          <div className="w-full md:w-[35%] md:min-w-[280px] md:max-w-[420px] md:shrink-0 space-y-1 order-1 md:order-none mobile-col-center contents md:block">
            <div className="order-1 md:order-none"><GistSync onSyncComplete={handleSyncComplete} /></div>
            <div className="order-1 md:order-none"><RecipeManager basicInfo={basicInfo} slotStates={slotStates}
              omega3Custom={omega3Custom} nutrientAdjust={nutrientAdjust}
              onLoadRecipe={handleLoadRecipe} resultRef={resultRef}
              daily={daily} totals={totals} dailyCalories={dailyCalories} /></div>
            <div className="order-1 md:order-none"><CustomIngredient onUpdate={handleCustomFoodUpdate} /></div>
            <div className="order-1 md:order-none"><Inventory onUpdate={handleCustomFoodUpdate} /></div>
            <div className="order-5 md:order-none"><SupplementSection slotStates={slotStates} onSlotUpdate={handleSlotUpdate} /></div>
          </div>

          {/* Right column — PC: 40% / Mobile: full width, split into ordered sections */}
          <div className="w-full md:w-[40%] md:min-w-[300px] md:max-w-[520px] space-y-1 order-3 md:order-none mobile-col-right contents md:block">
            <div className="order-6 md:order-none"><ResultPanel daily={daily} totals={totals} dailyCalories={dailyCalories}
              sufficiency={sufficiency} warnings={warnings} slotStates={slotStates} /></div>
            <div className="order-7 md:order-none"><DetailedResults daily={daily} sufficiency={sufficiency} slotStates={slotStates} /></div>
            <div className="order-9 md:order-none"><NutrientRecommendation sufficiency={sufficiency} daily={daily}
              dailyCalories={dailyCalories} isKitten={isKitten} recipeDays={basicInfo.recipeDays} totals={totals} /></div>
          </div>
        </div>

        {/* Reference info — outside capture area */}
        <div className="md:flex md:justify-end max-w-[1400px]">
          <div className="w-full md:w-[40%] md:min-w-[300px] md:max-w-[520px] md:text-right text-xs text-gray-500 leading-relaxed mt-2 pr-1 order-11">
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
  );
}

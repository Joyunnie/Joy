import { useCallback, useEffect, useRef, useState } from 'react';
import Modal from './Modal.tsx';

interface CellDetailViewProps {
  layoutId: number;
  row: number;
  col: number;
  drugs: string[];
  onSave: (drugs: string[]) => void;
  onClose: () => void;
}

export default function CellDetailView({
  row,
  col,
  drugs: initialDrugs,
  onSave,
  onClose,
}: CellDetailViewProps) {
  const [drugs, setDrugs] = useState<string[]>(initialDrugs);
  const [inputValue, setInputValue] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);

  // Drag state
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [dropIndex, setDropIndex] = useState<number | null>(null);

  // Touch drag state
  const touchState = useRef<{
    index: number;
    startX: number;
    startY: number;
    holdTimer: ReturnType<typeof setTimeout> | null;
    isDragging: boolean;
    chipEls: HTMLElement[];
    ghostEl: HTMLElement | null;
  } | null>(null);

  const save = useCallback(
    (updated: string[]) => {
      setDrugs(updated);
      onSave(updated);
    },
    [onSave],
  );

  function handleAdd() {
    const name = inputValue.trim();
    if (!name) return;
    const updated = [...drugs, name];
    save(updated);
    setInputValue('');
    // scroll to end
    setTimeout(() => {
      scrollRef.current?.scrollTo({ left: scrollRef.current.scrollWidth, behavior: 'smooth' });
    }, 50);
  }

  function handleRemove(index: number) {
    const updated = drugs.filter((_, i) => i !== index);
    save(updated);
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleAdd();
    }
  }

  // --- HTML5 Drag (desktop) ---
  function handleDragStart(e: React.DragEvent, index: number) {
    setDragIndex(index);
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', String(index));
  }

  function handleDragOver(e: React.DragEvent, index: number) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    setDropIndex(index);
  }

  function handleDragEnd() {
    if (dragIndex !== null && dropIndex !== null && dragIndex !== dropIndex) {
      const updated = [...drugs];
      const [moved] = updated.splice(dragIndex, 1);
      updated.splice(dropIndex, 0, moved);
      save(updated);
    }
    setDragIndex(null);
    setDropIndex(null);
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    handleDragEnd();
  }

  // --- Touch drag (mobile) ---
  function handleTouchStart(e: React.TouchEvent, index: number) {
    const touch = e.touches[0];
    const chipEl = (e.currentTarget as HTMLElement);
    const holdTimer = setTimeout(() => {
      if (!touchState.current) return;
      touchState.current.isDragging = true;
      chipEl.style.opacity = '0.5';
      chipEl.style.zIndex = '50';
    }, 300);

    touchState.current = {
      index,
      startX: touch.clientX,
      startY: touch.clientY,
      holdTimer,
      isDragging: false,
      chipEls: [],
      ghostEl: null,
    };
  }

  function handleTouchMove(e: React.TouchEvent) {
    if (!touchState.current) return;
    const ts = touchState.current;
    const touch = e.touches[0];

    if (!ts.isDragging) {
      // If moved too far before hold completes, cancel
      const dx = Math.abs(touch.clientX - ts.startX);
      const dy = Math.abs(touch.clientY - ts.startY);
      if (dx > 10 || dy > 10) {
        if (ts.holdTimer) clearTimeout(ts.holdTimer);
        touchState.current = null;
      }
      return;
    }

    e.preventDefault();

    // Find which chip the touch is over
    const container = scrollRef.current;
    if (!container) return;
    const chips = Array.from(container.querySelectorAll('[data-chip-index]')) as HTMLElement[];
    let newDropIdx = ts.index;

    for (const chip of chips) {
      const rect = chip.getBoundingClientRect();
      const midX = rect.left + rect.width / 2;
      const chipIdx = Number(chip.dataset.chipIndex);
      if (touch.clientX > midX && chipIdx > newDropIdx) {
        newDropIdx = chipIdx;
      } else if (touch.clientX < midX && chipIdx < newDropIdx) {
        newDropIdx = chipIdx;
      }
    }

    setDropIndex(newDropIdx);
    setDragIndex(ts.index);
  }

  function handleTouchEnd(_e: React.TouchEvent) {
    if (!touchState.current) return;
    const ts = touchState.current;

    if (ts.holdTimer) clearTimeout(ts.holdTimer);

    // Reset chip style
    const container = scrollRef.current;
    if (container) {
      const chip = container.querySelector(`[data-chip-index="${ts.index}"]`) as HTMLElement | null;
      if (chip) {
        chip.style.opacity = '';
        chip.style.zIndex = '';
      }
    }

    if (ts.isDragging && dragIndex !== null && dropIndex !== null && dragIndex !== dropIndex) {
      const updated = [...drugs];
      const [moved] = updated.splice(dragIndex, 1);
      updated.splice(dropIndex, 0, moved);
      save(updated);
    }

    touchState.current = null;
    setDragIndex(null);
    setDropIndex(null);
  }

  // Cleanup timers on unmount
  useEffect(() => {
    return () => {
      if (touchState.current?.holdTimer) {
        clearTimeout(touchState.current.holdTimer);
      }
    };
  }, []);

  return (
    <Modal isOpen onClose={onClose} title={`${row + 1}행 ${col + 1}열 약품 관리`}>
      <div className="space-y-4">
        {/* Drug chips - horizontal scroll */}
        <div>
          <p className="text-xs text-gray-500 mb-2">
            약품 목록 ({drugs.length}개)
            {drugs.length > 0 && ' — 길게 눌러 순서 변경'}
          </p>
          <div
            ref={scrollRef}
            className="flex gap-2 overflow-x-auto pb-2 min-h-[44px] items-center"
            onDrop={handleDrop}
            onDragOver={(e) => e.preventDefault()}
          >
            {drugs.length === 0 && (
              <p className="text-sm text-gray-300 px-2">약품을 추가해 주세요</p>
            )}
            {drugs.map((drug, i) => (
              <div
                key={`${drug}-${i}`}
                data-chip-index={i}
                draggable
                onDragStart={(e) => handleDragStart(e, i)}
                onDragOver={(e) => handleDragOver(e, i)}
                onDragEnd={handleDragEnd}
                onTouchStart={(e) => handleTouchStart(e, i)}
                onTouchMove={(e) => handleTouchMove(e)}
                onTouchEnd={(e) => handleTouchEnd(e)}
                className={`
                  flex-shrink-0 flex items-center gap-1 px-3 py-1.5 rounded-full text-sm
                  border cursor-grab select-none touch-none transition-all
                  ${dragIndex === i ? 'opacity-50 border-blue-400 bg-blue-100' : 'border-gray-300 bg-white'}
                  ${dropIndex === i && dragIndex !== i ? 'ring-2 ring-blue-400 ring-offset-1' : ''}
                `}
              >
                <span className="whitespace-nowrap text-gray-800">{drug}</span>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleRemove(i);
                  }}
                  className="ml-0.5 w-4 h-4 flex items-center justify-center text-gray-400 hover:text-red-500 text-xs rounded-full hover:bg-red-50"
                >
                  &times;
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* Add drug input */}
        <div className="flex gap-2">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="약품명 입력..."
            className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            autoFocus
          />
          <button
            onClick={handleAdd}
            disabled={!inputValue.trim()}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg disabled:opacity-50 transition-colors flex-shrink-0"
          >
            추가
          </button>
        </div>
      </div>
    </Modal>
  );
}

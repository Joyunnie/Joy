import { useCallback, useRef, useState } from 'react';
import { parseKoreanDate, type ParseResult } from '../../utils/koreanDateParser.ts';
import DateHighlighter from './DateHighlighter.tsx';
import type { TodoCreateRequest } from '../../api/todos.ts';

interface TodoQuickAddProps {
  open: boolean;
  onClose: () => void;
  onSave: (req: TodoCreateRequest) => void;
}

const PRIORITY_OPTIONS = [
  { value: 1, label: 'P1', color: 'bg-red-500' },
  { value: 2, label: 'P2', color: 'bg-orange-400' },
  { value: 3, label: 'P3', color: 'bg-blue-400' },
  { value: 4, label: 'P4', color: 'bg-gray-300' },
] as const;

export default function TodoQuickAdd({ open, onClose, onSave }: TodoQuickAddProps) {
  const [input, setInput] = useState('');
  const [parseResult, setParseResult] = useState<ParseResult | null>(null);
  const [priority, setPriority] = useState(4);
  const [description, setDescription] = useState('');
  const [showDescription, setShowDescription] = useState(false);
  const [manualDate, setManualDate] = useState('');
  const [manualTime, setManualTime] = useState('');
  const [showDatePicker, setShowDatePicker] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleInputChange = useCallback((value: string) => {
    setInput(value);
    if (value.trim()) {
      setParseResult(parseKoreanDate(value));
    } else {
      setParseResult(null);
    }
  }, []);

  function handleSave() {
    if (!input.trim()) return;

    const parsed = parseResult;
    const title = parsed?.title || input.trim();

    let due_date: string | undefined;
    if (manualDate) {
      const dateStr = manualTime
        ? `${manualDate}T${manualTime}:00`
        : `${manualDate}T00:00:00`;
      due_date = new Date(dateStr).toISOString();
    } else if (parsed?.dueDate) {
      due_date = parsed.dueDate.toISOString();
    }

    onSave({ title, description: description || undefined, due_date, priority });

    // Reset
    setInput('');
    setParseResult(null);
    setPriority(4);
    setDescription('');
    setShowDescription(false);
    setManualDate('');
    setManualTime('');
    setShowDatePicker(false);
    onClose();
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.nativeEvent.isComposing) {
      e.preventDefault();
      handleSave();
    }
  }

  if (!open) return null;

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/30 z-40" onClick={onClose} />

      {/* Panel */}
      <div className="fixed bottom-0 left-0 right-0 bg-white rounded-t-2xl shadow-xl z-50 max-w-lg mx-auto animate-slide-up">
        <div className="p-4">
          {/* Handle */}
          <div className="w-10 h-1 bg-gray-300 rounded-full mx-auto mb-4" />

          {/* Input */}
          <div className="relative">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => handleInputChange(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="할일 입력... (예: 내일 오후 3시 약품 발주)"
              className="w-full px-4 py-3 text-sm border border-gray-200 rounded-xl focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400"
              autoFocus
            />
          </div>

          {/* Parsed preview */}
          {parseResult && (parseResult.dueDate || parseResult.highlights.length > 0) && (
            <div className="mt-2 px-2">
              <div className="text-xs text-gray-500 mb-1">
                <DateHighlighter text={input} highlights={parseResult.highlights} />
              </div>
              <div className="flex gap-2 flex-wrap">
                {parseResult.dueDate && (
                  <span className="inline-flex items-center px-2 py-0.5 bg-blue-50 text-blue-600 text-xs rounded-full">
                    {parseResult.dueDate.toLocaleDateString('ko-KR', {
                      month: 'short',
                      day: 'numeric',
                      weekday: 'short',
                    })}
                  </span>
                )}
                {parseResult.dueTime && (
                  <span className="inline-flex items-center px-2 py-0.5 bg-purple-50 text-purple-600 text-xs rounded-full">
                    {parseResult.dueTime}
                  </span>
                )}
              </div>
            </div>
          )}

          {/* Manual date picker */}
          {showDatePicker && (
            <div className="mt-3 flex gap-2">
              <input
                type="date"
                value={manualDate}
                onChange={(e) => setManualDate(e.target.value)}
                className="flex-1 px-3 py-2 text-sm border border-gray-200 rounded-lg"
              />
              <input
                type="time"
                value={manualTime}
                onChange={(e) => setManualTime(e.target.value)}
                className="w-28 px-3 py-2 text-sm border border-gray-200 rounded-lg"
              />
            </div>
          )}

          {/* Description */}
          {showDescription && (
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="메모 추가..."
              className="w-full mt-3 px-3 py-2 text-sm border border-gray-200 rounded-lg resize-none h-20 focus:outline-none focus:border-blue-400"
            />
          )}

          {/* Action bar */}
          <div className="mt-3 flex items-center justify-between">
            <div className="flex gap-2">
              {/* Date picker toggle */}
              <button
                onClick={() => setShowDatePicker(!showDatePicker)}
                className={`p-2 rounded-lg text-sm ${
                  showDatePicker ? 'bg-blue-100 text-blue-600' : 'bg-gray-100 text-gray-600'
                }`}
                title="날짜 선택"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
              </button>

              {/* Priority */}
              <div className="flex gap-1">
                {PRIORITY_OPTIONS.map((p) => (
                  <button
                    key={p.value}
                    onClick={() => setPriority(p.value)}
                    className={`w-7 h-7 rounded-lg text-xs font-bold ${
                      priority === p.value
                        ? `${p.color} text-white`
                        : 'bg-gray-100 text-gray-500'
                    }`}
                  >
                    {p.label}
                  </button>
                ))}
              </div>

              {/* Memo toggle */}
              <button
                onClick={() => setShowDescription(!showDescription)}
                className={`p-2 rounded-lg text-sm ${
                  showDescription ? 'bg-blue-100 text-blue-600' : 'bg-gray-100 text-gray-600'
                }`}
                title="메모"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h7" />
                </svg>
              </button>
            </div>

            {/* Save */}
            <button
              onClick={handleSave}
              disabled={!input.trim()}
              className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg disabled:opacity-40 hover:bg-blue-700 transition-colors"
            >
              저장
            </button>
          </div>
        </div>
      </div>
    </>
  );
}

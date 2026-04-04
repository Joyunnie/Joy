import { useCallback, useEffect, useState } from 'react';
import type { TodoItem } from '../../api/todos.ts';
import { parseKoreanDate } from '../../utils/koreanDateParser.ts';

interface TodoDetailProps {
  todo: TodoItem;
  onClose: () => void;
  onUpdate: (id: number, data: Record<string, unknown>) => void;
  onDelete: (id: number) => void;
  onToggle: (id: number) => void;
}

const PRIORITY_OPTIONS = [
  { value: 1, label: 'P1 긴급', color: 'bg-red-500' },
  { value: 2, label: 'P2 높음', color: 'bg-orange-400' },
  { value: 3, label: 'P3 보통', color: 'bg-blue-400' },
  { value: 4, label: 'P4 낮음', color: 'bg-gray-300' },
] as const;

export default function TodoDetail({ todo, onClose, onUpdate, onDelete, onToggle }: TodoDetailProps) {
  const [title, setTitle] = useState(todo.title);
  const [description, setDescription] = useState(todo.description || '');
  const [priority, setPriority] = useState(todo.priority);
  const [dueDate, setDueDate] = useState('');
  const [dueTime, setDueTime] = useState('');
  const [dateInput, setDateInput] = useState('');
  const [showDateText, setShowDateText] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  useEffect(() => {
    if (todo.due_date) {
      const d = new Date(todo.due_date);
      setDueDate(d.toISOString().slice(0, 10));
      const h = d.getHours();
      const m = d.getMinutes();
      if (h || m) {
        setDueTime(`${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`);
      }
    }
  }, [todo.due_date]);

  const handleSave = useCallback(() => {
    const updates: Record<string, unknown> = {};
    if (title !== todo.title) updates.title = title;
    if (description !== (todo.description || '')) updates.description = description || null;
    if (priority !== todo.priority) updates.priority = priority;

    let newDueDate: string | null = null;
    if (dueDate) {
      const dateStr = dueTime ? `${dueDate}T${dueTime}:00` : `${dueDate}T00:00:00`;
      newDueDate = new Date(dateStr).toISOString();
    }
    const oldDue = todo.due_date ? new Date(todo.due_date).toISOString() : null;
    if (newDueDate !== oldDue) updates.due_date = newDueDate;

    if (Object.keys(updates).length > 0) {
      onUpdate(todo.id, updates);
    }
    onClose();
  }, [title, description, priority, dueDate, dueTime, todo, onUpdate, onClose]);

  function handleDateTextApply() {
    if (!dateInput.trim()) return;
    const parsed = parseKoreanDate(dateInput);
    if (parsed.dueDate) {
      setDueDate(parsed.dueDate.toISOString().slice(0, 10));
      if (parsed.dueTime) setDueTime(parsed.dueTime);
    }
    setDateInput('');
    setShowDateText(false);
  }

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/30 z-40" onClick={handleSave} />

      {/* Panel */}
      <div className="fixed bottom-0 left-0 right-0 bg-white rounded-t-2xl shadow-xl z-50 max-w-lg mx-auto max-h-[85vh] overflow-y-auto">
        <div className="p-4">
          {/* Handle */}
          <div className="w-10 h-1 bg-gray-300 rounded-full mx-auto mb-4" />

          {/* Header */}
          <div className="flex items-center justify-between mb-4">
            <button
              onClick={() => onToggle(todo.id)}
              className={`px-3 py-1 rounded-full text-xs font-medium ${
                todo.is_completed
                  ? 'bg-green-100 text-green-700'
                  : 'bg-gray-100 text-gray-600'
              }`}
            >
              {todo.is_completed ? '완료됨' : '미완료'}
            </button>
            <button
              onClick={handleSave}
              className="text-blue-600 text-sm font-medium"
            >
              저장
            </button>
          </div>

          {/* Title */}
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="w-full text-lg font-medium text-gray-800 border-b border-gray-100 pb-2 mb-4 focus:outline-none focus:border-blue-400"
          />

          {/* Due date */}
          <div className="mb-4">
            <label className="text-xs text-gray-500 font-medium block mb-1">마감일</label>
            <div className="flex gap-2">
              <input
                type="date"
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
                className="flex-1 px-3 py-2 text-sm border border-gray-200 rounded-lg"
              />
              <input
                type="time"
                value={dueTime}
                onChange={(e) => setDueTime(e.target.value)}
                className="w-28 px-3 py-2 text-sm border border-gray-200 rounded-lg"
              />
            </div>
            {!showDateText ? (
              <button
                onClick={() => setShowDateText(true)}
                className="mt-1 text-xs text-blue-500"
              >
                자연어로 입력
              </button>
            ) : (
              <div className="mt-2 flex gap-2">
                <input
                  type="text"
                  value={dateInput}
                  onChange={(e) => setDateInput(e.target.value)}
                  placeholder="예: 다음주 월요일, 내일 오후 3시"
                  className="flex-1 px-3 py-1.5 text-sm border border-gray-200 rounded-lg"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.nativeEvent.isComposing) handleDateTextApply();
                  }}
                />
                <button
                  onClick={handleDateTextApply}
                  className="px-3 py-1.5 bg-blue-500 text-white text-xs rounded-lg"
                >
                  적용
                </button>
              </div>
            )}
            {dueDate && (
              <button
                onClick={() => { setDueDate(''); setDueTime(''); }}
                className="mt-1 text-xs text-red-400"
              >
                날짜 제거
              </button>
            )}
          </div>

          {/* Priority */}
          <div className="mb-4">
            <label className="text-xs text-gray-500 font-medium block mb-1">우선순위</label>
            <div className="flex gap-2">
              {PRIORITY_OPTIONS.map((p) => (
                <button
                  key={p.value}
                  onClick={() => setPriority(p.value)}
                  className={`flex-1 py-2 rounded-lg text-xs font-medium transition-colors ${
                    priority === p.value
                      ? `${p.color} text-white`
                      : 'bg-gray-100 text-gray-600'
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          {/* Description */}
          <div className="mb-4">
            <label className="text-xs text-gray-500 font-medium block mb-1">메모</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="메모 추가..."
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg resize-none h-24 focus:outline-none focus:border-blue-400"
            />
          </div>

          {/* Meta */}
          <div className="text-xs text-gray-400 mb-4">
            작성: {new Date(todo.created_at).toLocaleDateString('ko-KR')}
          </div>

          {/* Delete */}
          {!showDeleteConfirm ? (
            <button
              onClick={() => setShowDeleteConfirm(true)}
              className="w-full py-2.5 text-red-500 text-sm font-medium border border-red-200 rounded-lg hover:bg-red-50 transition-colors"
            >
              삭제
            </button>
          ) : (
            <div className="flex gap-2">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                className="flex-1 py-2.5 text-sm text-gray-600 border border-gray-200 rounded-lg"
              >
                취소
              </button>
              <button
                onClick={() => onDelete(todo.id)}
                className="flex-1 py-2.5 text-sm text-white bg-red-500 rounded-lg"
              >
                삭제 확인
              </button>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

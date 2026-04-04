import type { TodoItem as TodoItemType } from '../../api/todos.ts';

interface TodoItemProps {
  todo: TodoItemType;
  onToggle: (id: number) => void;
  onSelect: (todo: TodoItemType) => void;
}

const PRIORITY_COLORS: Record<number, string> = {
  1: 'bg-red-500',
  2: 'bg-orange-400',
  3: 'bg-blue-400',
  4: '',
};

function formatDueDate(dateStr: string | null): { text: string; isOverdue: boolean } {
  if (!dateStr) return { text: '', isOverdue: false };
  const due = new Date(dateStr);
  const now = new Date();
  const isOverdue = due < now;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const tomorrow = new Date(today);
  tomorrow.setDate(tomorrow.getDate() + 1);
  const dueDay = new Date(due);
  dueDay.setHours(0, 0, 0, 0);

  let dayPart: string;
  if (dueDay.getTime() === today.getTime()) {
    dayPart = '오늘';
  } else if (dueDay.getTime() === tomorrow.getTime()) {
    dayPart = '내일';
  } else {
    dayPart = `${due.getMonth() + 1}/${due.getDate()}`;
  }

  const timePart =
    due.getHours() !== 0 || due.getMinutes() !== 0
      ? ` ${String(due.getHours()).padStart(2, '0')}:${String(due.getMinutes()).padStart(2, '0')}`
      : '';

  return { text: dayPart + timePart, isOverdue };
}

export default function TodoItem({ todo, onToggle, onSelect }: TodoItemProps) {
  const { text: dueText, isOverdue } = formatDueDate(todo.due_date);
  const priorityColor = PRIORITY_COLORS[todo.priority] || '';

  return (
    <div
      className="flex items-center gap-3 px-4 py-3 bg-white border-b border-gray-100 active:bg-gray-50"
      onClick={() => onSelect(todo)}
    >
      {/* Priority indicator */}
      {priorityColor && (
        <span className={`w-1 h-8 rounded-full flex-shrink-0 ${priorityColor}`} />
      )}

      {/* Checkbox */}
      <button
        onClick={(e) => {
          e.stopPropagation();
          onToggle(todo.id);
        }}
        className={`w-5 h-5 rounded border-2 flex-shrink-0 flex items-center justify-center transition-colors ${
          todo.is_completed
            ? 'bg-blue-500 border-blue-500'
            : 'border-gray-300 hover:border-blue-400'
        }`}
      >
        {todo.is_completed && (
          <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
          </svg>
        )}
      </button>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <p
          className={`text-sm truncate ${
            todo.is_completed ? 'line-through text-gray-400' : 'text-gray-800'
          }`}
        >
          {todo.title}
        </p>
        {dueText && (
          <p
            className={`text-xs mt-0.5 ${
              isOverdue && !todo.is_completed ? 'text-red-500 font-medium' : 'text-gray-400'
            }`}
          >
            {dueText}
          </p>
        )}
      </div>
    </div>
  );
}

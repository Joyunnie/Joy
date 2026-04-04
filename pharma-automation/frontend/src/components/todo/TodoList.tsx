import type { TodoItem as TodoItemType } from '../../api/todos.ts';
import TodoItem from './TodoItem.tsx';

interface TodoSection {
  label: string;
  items: TodoItemType[];
  color?: string;
}

interface TodoListProps {
  sections: TodoSection[];
  onToggle: (id: number) => void;
  onSelect: (todo: TodoItemType) => void;
}

export default function TodoList({ sections, onToggle, onSelect }: TodoListProps) {
  return (
    <div className="space-y-4">
      {sections.map((section) =>
        section.items.length === 0 ? null : (
          <div key={section.label}>
            <h3
              className={`text-xs font-bold uppercase tracking-wider px-4 py-1 ${
                section.color || 'text-gray-500'
              }`}
            >
              {section.label} ({section.items.length})
            </h3>
            <div className="bg-white rounded-lg overflow-hidden shadow-sm">
              {section.items.map((todo) => (
                <TodoItem
                  key={todo.id}
                  todo={todo}
                  onToggle={onToggle}
                  onSelect={onSelect}
                />
              ))}
            </div>
          </div>
        ),
      )}
    </div>
  );
}

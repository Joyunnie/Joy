import { useCallback, useEffect, useState } from 'react';
import { Plus } from 'lucide-react';
import PageHeader from '../components/common/PageHeader.tsx';
import {
  fetchTodos,
  createTodo,
  toggleComplete,
  updateTodo,
  deleteTodo,
  type TodoItem,
  type TodoCreateRequest,
} from '../api/todos.ts';
import TodoList from '../components/todo/TodoList.tsx';
import TodoQuickAdd from '../components/todo/TodoQuickAdd.tsx';
import TodoDetail from '../components/todo/TodoDetail.tsx';
import EmptyState from '../components/EmptyState.tsx';
import Spinner from '../components/Spinner.tsx';
import Toast from '../components/Toast.tsx';
import { useToast } from '../hooks/useToast.ts';

type Tab = 'today' | 'upcoming' | 'completed';

function groupByDate(items: TodoItem[]) {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const tomorrow = new Date(today);
  tomorrow.setDate(tomorrow.getDate() + 1);
  const nextWeek = new Date(today);
  nextWeek.setDate(nextWeek.getDate() + 7);
  const twoWeeks = new Date(today);
  twoWeeks.setDate(twoWeeks.getDate() + 14);

  const groups: Record<string, TodoItem[]> = {
    '내일': [],
    '이번주': [],
    '다음주': [],
    '이후': [],
  };

  for (const item of items) {
    if (!item.due_date) continue;
    const d = new Date(item.due_date);
    const day = new Date(d.getFullYear(), d.getMonth(), d.getDate());
    if (day.getTime() === tomorrow.getTime()) {
      groups['내일'].push(item);
    } else if (day < nextWeek) {
      groups['이번주'].push(item);
    } else if (day < twoWeeks) {
      groups['다음주'].push(item);
    } else {
      groups['이후'].push(item);
    }
  }

  return Object.entries(groups)
    .filter(([, items]) => items.length > 0)
    .map(([label, items]) => ({ label, items }));
}

export default function TodoPage() {
  const [tab, setTab] = useState<Tab>('today');
  const [overdue, setOverdue] = useState<TodoItem[]>([]);
  const [todayItems, setTodayItems] = useState<TodoItem[]>([]);
  const [noDate, setNoDate] = useState<TodoItem[]>([]);
  const [upcoming, setUpcoming] = useState<TodoItem[]>([]);
  const [completed, setCompleted] = useState<TodoItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [selectedTodo, setSelectedTodo] = useState<TodoItem | null>(null);
  const { toasts, showToast, removeToast } = useToast();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      if (tab === 'today') {
        const [overdueRes, todayRes, noDateRes] = await Promise.all([
          fetchTodos('overdue'),
          fetchTodos('today'),
          fetchTodos('no_date'),
        ]);
        setOverdue(overdueRes.items);
        setTodayItems(todayRes.items);
        setNoDate(noDateRes.items);
      } else if (tab === 'upcoming') {
        const res = await fetchTodos('upcoming');
        setUpcoming(res.items);
      } else {
        const res = await fetchTodos('completed', 'created_at');
        setCompleted(res.items);
      }
    } catch {
      showToast('할일을 불러오지 못했습니다', 'error');
    } finally {
      setLoading(false);
    }
  }, [tab, showToast]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleToggle(id: number) {
    try {
      await toggleComplete(id);
      load();
    } catch {
      showToast('상태 변경에 실패했습니다', 'error');
    }
  }

  async function handleCreate(req: TodoCreateRequest) {
    try {
      await createTodo(req);
      showToast('할일이 추가되었습니다', 'success');
      load();
    } catch {
      showToast('할��� 추가에 실패했습니다', 'error');
    }
  }

  async function handleUpdate(id: number, data: Record<string, unknown>) {
    try {
      await updateTodo(id, data);
      setSelectedTodo(null);
      load();
    } catch {
      showToast('수정에 실패했습니다', 'error');
    }
  }

  async function handleDelete(id: number) {
    try {
      await deleteTodo(id);
      setSelectedTodo(null);
      showToast('할일이 삭제되었습니다', 'success');
      load();
    } catch {
      showToast('삭제에 실패했습니다', 'error');
    }
  }

  const TABS: { key: Tab; label: string }[] = [
    { key: 'today', label: '오늘' },
    { key: 'upcoming', label: '예정' },
    { key: 'completed', label: '완료' },
  ];

  function renderContent() {
    if (loading) {
      return (
        <Spinner />
      );
    }

    if (tab === 'today') {
      const sections = [
        { label: '기한 지남', items: overdue, color: 'text-red-500' },
        { label: '오늘', items: todayItems, color: 'text-blue-600' },
        { label: '날짜 없음', items: noDate, color: 'text-gray-400' },
      ];
      const hasItems = sections.some((s) => s.items.length > 0);
      if (!hasItems) return <EmptyState message="오늘 할일이 없습니다" />;
      return (
        <TodoList
          sections={sections}
          onToggle={handleToggle}
          onSelect={setSelectedTodo}
        />
      );
    }

    if (tab === 'upcoming') {
      if (upcoming.length === 0) return <EmptyState message="예정된 할일이 없습니다" />;
      const groups = groupByDate(upcoming);
      return (
        <TodoList
          sections={groups}
          onToggle={handleToggle}
          onSelect={setSelectedTodo}
        />
      );
    }

    // completed
    if (completed.length === 0) return <EmptyState message="완료된 할일이 없습니다" />;
    return (
      <TodoList
        sections={[{ label: '최근 완료', items: completed, color: 'text-green-600' }]}
        onToggle={handleToggle}
        onSelect={setSelectedTodo}
      />
    );
  }

  return (
    <div className="p-4 pb-20 max-w-lg mx-auto">
      <Toast toasts={toasts} onRemove={removeToast} />

      <PageHeader title="할일" />

      {/* Segment tabs */}
      <div className="flex bg-gray-100 rounded-lg p-1 mb-4">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex-1 py-2 text-sm font-medium rounded-md transition-colors ${
              tab === t.key
                ? 'bg-white text-blue-600 shadow-sm'
                : 'text-gray-500'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {renderContent()}

      {/* FAB */}
      <button
        onClick={() => setShowAdd(true)}
        className="fixed bottom-20 right-4 w-14 h-14 bg-blue-600 text-white rounded-full shadow-lg flex items-center justify-center hover:bg-blue-700 transition-colors z-30"
      >
        <Plus size={24} />
      </button>

      {/* Quick add panel */}
      <TodoQuickAdd
        open={showAdd}
        onClose={() => setShowAdd(false)}
        onSave={handleCreate}
      />

      {/* Detail panel */}
      {selectedTodo && (
        <TodoDetail
          todo={selectedTodo}
          onClose={() => setSelectedTodo(null)}
          onUpdate={handleUpdate}
          onDelete={handleDelete}
          onToggle={handleToggle}
        />
      )}
    </div>
  );
}

import api from './client.ts';

export interface TodoItem {
  id: number;
  pharmacy_id: number;
  title: string;
  description: string | null;
  due_date: string | null;
  priority: number;
  is_completed: boolean;
  completed_at: string | null;
  completed_by: number | null;
  created_by: number;
  created_at: string;
  updated_at: string;
  sort_order: number;
}

export interface TodoListResponse {
  items: TodoItem[];
  total: number;
}

export type TodoFilter = 'today' | 'upcoming' | 'completed' | 'overdue' | 'no_date' | 'all';

export interface TodoCreateRequest {
  title: string;
  description?: string;
  due_date?: string;
  priority?: number;
}

export interface TodoUpdateRequest {
  title?: string;
  description?: string;
  due_date?: string | null;
  priority?: number;
}

export async function fetchTodos(
  filter: TodoFilter = 'all',
  sort: string = 'due_date',
  limit = 50,
  offset = 0,
): Promise<TodoListResponse> {
  const { data } = await api.get<TodoListResponse>('/todos', {
    params: { filter, sort, limit, offset },
  });
  return data;
}

export async function createTodo(body: TodoCreateRequest): Promise<TodoItem> {
  const { data } = await api.post<TodoItem>('/todos', body);
  return data;
}

export async function getTodo(id: number): Promise<TodoItem> {
  const { data } = await api.get<TodoItem>(`/todos/${id}`);
  return data;
}

export async function updateTodo(id: number, body: TodoUpdateRequest): Promise<TodoItem> {
  const { data } = await api.put<TodoItem>(`/todos/${id}`, body);
  return data;
}

export async function deleteTodo(id: number): Promise<void> {
  await api.delete(`/todos/${id}`);
}

export async function toggleComplete(id: number): Promise<TodoItem> {
  const { data } = await api.patch<TodoItem>(`/todos/${id}/complete`);
  return data;
}

export async function rescheduleTodo(id: number, due_date: string): Promise<TodoItem> {
  const { data } = await api.patch<TodoItem>(`/todos/${id}/reschedule`, { due_date });
  return data;
}

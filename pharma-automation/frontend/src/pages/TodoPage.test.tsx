import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from '../test/mocks/server';
import TestWrapper from '../test/TestWrapper';
import TodoPage from './TodoPage';

describe('TodoPage', () => {
  it('shows empty state when no todos', async () => {
    render(
      <TestWrapper>
        <TodoPage />
      </TestWrapper>,
    );

    // Default tab is "오늘" which shows "오늘 할일이 없습니다" when empty
    await waitFor(() => {
      expect(screen.getByText('오늘 할일이 없습니다')).toBeInTheDocument();
    });
  });

  it('renders todo list', async () => {
    const todo = {
      id: 1, pharmacy_id: 7, title: '약품 발주',
      description: null, due_date: null, priority: 2,
      is_completed: false, completed_at: null, completed_by: null,
      created_by: 1, created_at: '2026-04-10T10:00:00Z',
      updated_at: '2026-04-10T10:00:00Z', sort_order: 0,
    };

    server.use(
      // The today tab fetches overdue, today, and no_date filters
      http.get('/api/v1/todos', ({ request }) => {
        const url = new URL(request.url);
        const filter = url.searchParams.get('filter');
        if (filter === 'today') {
          return HttpResponse.json({ items: [todo], total: 1 });
        }
        return HttpResponse.json({ items: [], total: 0 });
      }),
    );

    render(
      <TestWrapper>
        <TodoPage />
      </TestWrapper>,
    );

    await waitFor(() => {
      expect(screen.getByText('약품 발주')).toBeInTheDocument();
    });
  });

  it('shows tab buttons', async () => {
    render(
      <TestWrapper>
        <TodoPage />
      </TestWrapper>,
    );

    await waitFor(() => {
      expect(screen.getByText('오늘')).toBeInTheDocument();
    });
  });
});

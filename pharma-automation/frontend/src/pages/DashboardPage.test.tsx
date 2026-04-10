import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, it, expect } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from '../test/mocks/server';
import TestWrapper, { setupFakeAuth } from '../test/TestWrapper';
import DashboardPage from './DashboardPage';

describe('DashboardPage', () => {
  beforeEach(() => setupFakeAuth());
  it('shows loading spinner initially', () => {
    const { container } = render(
      <TestWrapper>
        <DashboardPage />
      </TestWrapper>,
    );
    expect(container.querySelector('.animate-spin')).toBeInTheDocument();
  });

  it('renders dashboard data after loading', async () => {
    server.use(
      http.get('/api/v1/alerts', () =>
        HttpResponse.json({
          alerts: [{ id: 1, alert_type: 'LOW_STOCK', message: '재고 부족 알림', sent_at: new Date().toISOString(), read_at: null }],
          total: 1,
        }),
      ),
      http.get('/api/v1/predictions', () =>
        HttpResponse.json({ predictions: [], total: 0 }),
      ),
      http.get('/api/v1/todos', () =>
        HttpResponse.json({ items: [], total: 0 }),
      ),
    );

    render(
      <TestWrapper>
        <DashboardPage />
      </TestWrapper>,
    );

    await waitFor(() => {
      expect(screen.getByText('대시보드')).toBeInTheDocument();
    });
  });

  it('shows error message on API failure', async () => {
    server.use(
      http.get('/api/v1/alerts', () => HttpResponse.error()),
      http.get('/api/v1/otc-inventory', () => HttpResponse.error()),
      http.get('/api/v1/narcotics-inventory', () => HttpResponse.error()),
      http.get('/api/v1/inventory/status', () => HttpResponse.error()),
      http.get('/api/v1/predictions', () => HttpResponse.error()),
      http.get('/api/v1/todos', () => HttpResponse.error()),
    );

    render(
      <TestWrapper>
        <DashboardPage />
      </TestWrapper>,
    );

    await waitFor(() => {
      expect(screen.getByText('데이터를 불러오지 못했습니다')).toBeInTheDocument();
    });
  });
});

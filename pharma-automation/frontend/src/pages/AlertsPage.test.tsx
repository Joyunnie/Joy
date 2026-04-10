import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from '../test/mocks/server';
import TestWrapper from '../test/TestWrapper';
import AlertsPage from './AlertsPage';

describe('AlertsPage', () => {
  it('shows empty state when no alerts', async () => {
    render(
      <TestWrapper>
        <AlertsPage />
      </TestWrapper>,
    );

    await waitFor(() => {
      expect(screen.getByText('알림이 없습니다')).toBeInTheDocument();
    });
  });

  it('renders alert list', async () => {
    server.use(
      http.get('/api/v1/alerts', () =>
        HttpResponse.json({
          alerts: [
            { id: 1, alert_type: 'LOW_STOCK', message: '아모시실린 재고 부족', sent_at: '2026-04-10T10:00:00Z', read_at: null },
            { id: 2, alert_type: 'NARCOTICS_LOW', message: '펜타닐 재고 부족', sent_at: '2026-04-10T09:00:00Z', read_at: null },
          ],
          total: 2,
        }),
      ),
    );

    render(
      <TestWrapper>
        <AlertsPage />
      </TestWrapper>,
    );

    await waitFor(() => {
      expect(screen.getByText('아모시실린 재고 부족')).toBeInTheDocument();
      expect(screen.getByText('펜타닐 재고 부족')).toBeInTheDocument();
    });
  });

  it('renders filter chips', async () => {
    render(
      <TestWrapper>
        <AlertsPage />
      </TestWrapper>,
    );

    await waitFor(() => {
      // Both type filter and read filter have "전체", so use getAllByText
      expect(screen.getAllByText('전체')).toHaveLength(2);
      expect(screen.getByText('재고부족')).toBeInTheDocument();
      expect(screen.getByText('마약류')).toBeInTheDocument();
      expect(screen.getByText('내원예측')).toBeInTheDocument();
    });
  });
});

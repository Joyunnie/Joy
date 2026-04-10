/**
 * MSW request handlers for API mocking in tests.
 * Each handler returns minimal valid responses matching the backend schemas.
 */
import { http, HttpResponse } from 'msw';

/** Default handlers — happy path with empty/minimal data. */
export const handlers = [
  // Alerts
  http.get('/api/v1/alerts', () =>
    HttpResponse.json({ alerts: [], total: 0 }),
  ),

  http.patch('/api/v1/alerts/:id/read', () =>
    HttpResponse.json({ id: 1, read_at: new Date().toISOString() }),
  ),

  // OTC Inventory
  http.get('/api/v1/otc-inventory', () =>
    HttpResponse.json({ items: [], total: 0 }),
  ),

  // Narcotics
  http.get('/api/v1/narcotics-inventory', () =>
    HttpResponse.json({ items: [], total: 0 }),
  ),

  // Prescription inventory status
  http.get('/api/v1/inventory/status', () =>
    HttpResponse.json({ items: [] }),
  ),

  // Predictions
  http.get('/api/v1/predictions', () =>
    HttpResponse.json({ predictions: [], total: 0 }),
  ),

  // Todos
  http.get('/api/v1/todos', () =>
    HttpResponse.json({ items: [], total: 0 }),
  ),

  http.post('/api/v1/todos', () =>
    HttpResponse.json({
      id: 1, pharmacy_id: 7, title: 'New', description: null,
      due_date: null, priority: 4, is_completed: false,
      completed_at: null, completed_by: null, created_by: 1,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      sort_order: 0,
    }, { status: 201 }),
  ),

  http.patch('/api/v1/todos/:id/complete', ({ params }) =>
    HttpResponse.json({
      id: Number(params.id), pharmacy_id: 7, title: 'Done',
      description: null, due_date: null, priority: 4,
      is_completed: true,
      completed_at: new Date().toISOString(),
      completed_by: 1, created_by: 1,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      sort_order: 0,
    }),
  ),
];

import api from './client.ts';
import type { AlertListResponse, AlertReadResponse } from '../types/api.ts';

export interface FetchAlertsParams {
  limit?: number;
  offset?: number;
  alert_type?: string;
  is_read?: boolean;
}

export async function fetchAlerts(params: FetchAlertsParams = {}): Promise<AlertListResponse> {
  const { data } = await api.get<AlertListResponse>('/alerts', { params });
  return data;
}

export async function markAlertRead(id: number): Promise<AlertReadResponse> {
  const { data } = await api.patch<AlertReadResponse>(`/alerts/${id}/read`);
  return data;
}

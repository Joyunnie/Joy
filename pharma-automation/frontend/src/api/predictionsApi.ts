import api from './client.ts';
import type { PredictionListResponse } from '../types/api.ts';

export async function fetchPredictions(daysAhead: number): Promise<PredictionListResponse> {
  const { data } = await api.get<PredictionListResponse>('/predictions', {
    params: { days_ahead: daysAhead },
  });
  return data;
}

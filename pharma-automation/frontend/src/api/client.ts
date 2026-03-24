import axios from 'axios';
import type { AccessTokenResponse } from '../types/api.ts';

const api = axios.create({
  baseURL: '/api/v1',
});

// --- Request interceptor: attach JWT ---

api.interceptors.request.use((config) => {
  // TODO: 프로덕션 배포 시 httpOnly 쿠키 전환 검토
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// --- Response interceptor: auto-refresh on 401 ---

let isRefreshing = false;
let failedQueue: Array<{
  resolve: (token: string) => void;
  reject: (err: unknown) => void;
}> = [];

function processQueue(error: unknown, token: string | null) {
  for (const prom of failedQueue) {
    if (token) {
      prom.resolve(token);
    } else {
      prom.reject(error);
    }
  }
  failedQueue = [];
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status !== 401 || originalRequest._retry) {
      return Promise.reject(error);
    }

    if (isRefreshing) {
      return new Promise((resolve, reject) => {
        failedQueue.push({
          resolve: (token: string) => {
            originalRequest.headers.Authorization = `Bearer ${token}`;
            resolve(api(originalRequest));
          },
          reject,
        });
      });
    }

    originalRequest._retry = true;
    isRefreshing = true;

    // TODO: 프로덕션 배포 시 httpOnly 쿠키 전환 검토
    const refreshToken = localStorage.getItem('refresh_token');
    if (!refreshToken) {
      isRefreshing = false;
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      window.location.href = '/login';
      return Promise.reject(error);
    }

    try {
      const { data } = await axios.post<AccessTokenResponse>(
        '/api/v1/auth/refresh',
        { refresh_token: refreshToken },
      );

      // TODO: 프로덕션 배포 시 httpOnly 쿠키 전환 검토
      localStorage.setItem('access_token', data.access_token);

      originalRequest.headers.Authorization = `Bearer ${data.access_token}`;
      processQueue(null, data.access_token);
      return api(originalRequest);
    } catch (refreshError) {
      processQueue(refreshError, null);
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      window.location.href = '/login';
      return Promise.reject(refreshError);
    } finally {
      isRefreshing = false;
    }
  },
);

export default api;

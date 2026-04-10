/**
 * Test wrapper that provides Router + AuthContext for page tests.
 * Call setupFakeAuth() in beforeEach before rendering.
 */
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { AuthProvider } from '../contexts/AuthContext';

// Fake JWT token (base64-encoded header.payload.signature)
// Payload: { sub: "1", pharmacy_id: 7, role: "PHARMACIST", type: "access", iat: 9999999999, exp: 9999999999 }
const FAKE_ACCESS_TOKEN = [
  btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' })),
  btoa(JSON.stringify({
    sub: '1', pharmacy_id: 7, role: 'PHARMACIST',
    type: 'access', iat: 9999999999, exp: 9999999999,
  })),
  'fake-signature',
].join('.');

/** Call in beforeEach — sets localStorage tokens before render. */
export function setupFakeAuth() {
  localStorage.setItem('access_token', FAKE_ACCESS_TOKEN);
  localStorage.setItem('refresh_token', 'fake-refresh');
}

interface Props {
  children: ReactNode;
  initialRoute?: string;
}

export default function TestWrapper({ children, initialRoute = '/' }: Props) {
  return (
    <MemoryRouter initialEntries={[initialRoute]}>
      <AuthProvider>
        {children}
      </AuthProvider>
    </MemoryRouter>
  );
}

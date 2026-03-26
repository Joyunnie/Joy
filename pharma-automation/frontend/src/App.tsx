import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext.tsx';
import ProtectedRoute from './components/ProtectedRoute.tsx';
import Layout from './components/Layout.tsx';
import LoginPage from './pages/LoginPage.tsx';
import DashboardPage from './pages/DashboardPage.tsx';
import InventoryPage from './pages/InventoryPage.tsx';
import AlertsPage from './pages/AlertsPage.tsx';
import PredictionsPage from './pages/PredictionsPage.tsx';
import ThresholdsPage from './pages/ThresholdsPage.tsx';
import ShelfViewPage from './pages/ShelfViewPage.tsx';

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<ProtectedRoute />}>
            <Route element={<Layout />}>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/inventory" element={<InventoryPage />} />
              <Route path="/predictions" element={<PredictionsPage />} />
              <Route path="/alerts" element={<AlertsPage />} />
              <Route path="/thresholds" element={<ThresholdsPage />} />
              <Route path="/shelf" element={<ShelfViewPage />} />
            </Route>
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

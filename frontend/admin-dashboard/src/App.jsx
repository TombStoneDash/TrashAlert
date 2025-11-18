import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import DashboardLayout from './components/Layout/DashboardLayout';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Cities from './pages/Cities';
import Addresses from './pages/Addresses';
import CrowdReports from './pages/CrowdReports';
import Schedules from './pages/Schedules';
import Consensus from './pages/Consensus';
import Logs from './pages/Logs';
import Leaderboard from './pages/Leaderboard';

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />

          <Route
            element={
              <ProtectedRoute>
                <DashboardLayout />
              </ProtectedRoute>
            }
          >
            <Route path="/" element={<Dashboard />} />
            <Route path="/cities" element={<Cities />} />
            <Route path="/addresses" element={<Addresses />} />
            <Route path="/reports" element={<CrowdReports />} />
            <Route path="/schedules" element={<Schedules />} />
            <Route path="/consensus" element={<Consensus />} />
            <Route path="/logs" element={<Logs />} />
            <Route path="/leaderboard" element={<Leaderboard />} />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;

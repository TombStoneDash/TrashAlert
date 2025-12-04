import { Link, useLocation } from 'react-router-dom';
import {
  Home,
  MapPin,
  Building2,
  Flag,
  Calendar,
  CheckCircle,
  FileText,
  Truck,
  LogOut,
  Flame,
  Trophy,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

const Sidebar = () => {
  const location = useLocation();
  const { logout } = useAuth();

  const menuItems = [
    { path: '/', icon: Home, label: 'Dashboard' },
    { path: '/cities', icon: Building2, label: 'Cities' },
    { path: '/addresses', icon: MapPin, label: 'Addresses' },
    { path: '/trucks', icon: Truck, label: 'Truck Tracking' },
    { path: '/reports', icon: Flag, label: 'Crowd Reports' },
    { path: '/schedules', icon: Calendar, label: 'Schedules' },
    { path: '/consensus', icon: CheckCircle, label: 'Consensus Status' },
    { path: '/heatmap', icon: Flame, label: 'Heatmap Analytics' },
    { path: '/leaderboard', icon: Trophy, label: 'Leaderboard' },
    { path: '/logs', icon: FileText, label: 'Logs' },
  ];

  const isActive = (path) => {
    if (path === '/') return location.pathname === '/';
    return location.pathname.startsWith(path);
  };

  return (
    <div className="w-64 bg-gray-900 text-white min-h-screen flex flex-col">
      <div className="p-6">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          🗑️ TrashAlert
        </h1>
        <p className="text-sm text-gray-400 mt-1">Admin Dashboard</p>
      </div>

      <nav className="flex-1 px-3">
        {menuItems.map((item) => {
          const Icon = item.icon;
          return (
            <Link
              key={item.path}
              to={item.path}
              className={`flex items-center gap-3 px-4 py-3 rounded-lg mb-1 transition-colors ${
                isActive(item.path)
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-300 hover:bg-gray-800'
              }`}
            >
              <Icon size={20} />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="p-3">
        <button
          onClick={logout}
          className="flex items-center gap-3 px-4 py-3 rounded-lg w-full text-gray-300 hover:bg-gray-800 transition-colors"
        >
          <LogOut size={20} />
          <span>Logout</span>
        </button>
      </div>
    </div>
  );
};

export default Sidebar;

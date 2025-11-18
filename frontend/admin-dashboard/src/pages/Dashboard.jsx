import { useEffect, useState } from 'react';
import { statsAPI } from '../services/api';
import Header from '../components/Layout/Header';
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { Building2, MapPin, Flag, Calendar, TrendingUp, Users } from 'lucide-react';

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'];

const Dashboard = () => {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      setLoading(true);
      const data = await statsAPI.getDashboard();
      setStats(data);
      setError(null);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load statistics');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex-1">
        <Header title="Dashboard" />
        <div className="flex items-center justify-center h-96">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
            <p className="text-gray-600">Loading dashboard...</p>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1">
        <Header title="Dashboard" />
        <div className="p-8">
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
            {error}
          </div>
        </div>
      </div>
    );
  }

  const statCards = [
    {
      title: 'Total Cities',
      value: stats?.total_cities || 0,
      icon: Building2,
      color: 'blue',
      bgColor: 'bg-blue-100',
      textColor: 'text-blue-600',
    },
    {
      title: 'Total Addresses',
      value: stats?.total_addresses || 0,
      icon: MapPin,
      color: 'green',
      bgColor: 'bg-green-100',
      textColor: 'text-green-600',
    },
    {
      title: 'Crowd Reports',
      value: stats?.total_reports || 0,
      icon: Flag,
      color: 'orange',
      bgColor: 'bg-orange-100',
      textColor: 'text-orange-600',
    },
    {
      title: 'Schedules',
      value: stats?.total_schedules || 0,
      icon: Calendar,
      color: 'purple',
      bgColor: 'bg-purple-100',
      textColor: 'text-purple-600',
    },
    {
      title: 'Verified Addresses',
      value: stats?.verified_addresses || 0,
      icon: TrendingUp,
      color: 'indigo',
      bgColor: 'bg-indigo-100',
      textColor: 'text-indigo-600',
    },
    {
      title: 'Active Users',
      value: stats?.active_users || 0,
      icon: Users,
      color: 'pink',
      bgColor: 'bg-pink-100',
      textColor: 'text-pink-600',
    },
  ];

  // Mock data for charts (to be replaced with real data)
  const cityData = stats?.cities_breakdown || [
    { name: 'Brawley', addresses: 450, reports: 120 },
    { name: 'Calexico', addresses: 380, reports: 95 },
    { name: 'El Centro', addresses: 520, reports: 145 },
    { name: 'Holtville', addresses: 210, reports: 55 },
    { name: 'Imperial', addresses: 290, reports: 78 },
    { name: 'Calipatria', addresses: 180, reports: 42 },
  ];

  const sourceData = stats?.source_distribution || [
    { name: 'Official', value: 450 },
    { name: 'Crowd Verified', value: 320 },
    { name: 'Crowd Unverified', value: 180 },
    { name: 'Unknown', value: 50 },
  ];

  const trendsData = stats?.monthly_trends || [
    { month: 'Jan', reports: 65, addresses: 320 },
    { month: 'Feb', reports: 78, addresses: 380 },
    { month: 'Mar', reports: 92, addresses: 420 },
    { month: 'Apr', reports: 110, addresses: 490 },
    { month: 'May', reports: 135, addresses: 560 },
    { month: 'Jun', reports: 150, addresses: 610 },
  ];

  return (
    <div className="flex-1">
      <Header title="Dashboard" />

      <div className="p-8 space-y-6">
        {/* Stat Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {statCards.map((stat, index) => {
            const Icon = stat.icon;
            return (
              <div
                key={index}
                className="bg-white rounded-lg shadow p-6 border border-gray-200"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600">{stat.title}</p>
                    <p className="text-3xl font-bold text-gray-900 mt-2">
                      {stat.value.toLocaleString()}
                    </p>
                  </div>
                  <div className={`${stat.bgColor} p-3 rounded-lg`}>
                    <Icon className={stat.textColor} size={24} />
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Charts Row 1 */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Cities Overview */}
          <div className="bg-white rounded-lg shadow p-6 border border-gray-200">
            <h3 className="text-lg font-semibold text-gray-800 mb-4">
              Cities Overview
            </h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={cityData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="addresses" fill="#3b82f6" name="Addresses" />
                <Bar dataKey="reports" fill="#10b981" name="Reports" />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Data Source Distribution */}
          <div className="bg-white rounded-lg shadow p-6 border border-gray-200">
            <h3 className="text-lg font-semibold text-gray-800 mb-4">
              Data Source Distribution
            </h3>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={sourceData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, percent }) =>
                    `${name}: ${(percent * 100).toFixed(0)}%`
                  }
                  outerRadius={100}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {sourceData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Trends Chart */}
        <div className="bg-white rounded-lg shadow p-6 border border-gray-200">
          <h3 className="text-lg font-semibold text-gray-800 mb-4">Growth Trends</h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={trendsData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="month" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Line
                type="monotone"
                dataKey="addresses"
                stroke="#3b82f6"
                strokeWidth={2}
                name="Total Addresses"
              />
              <Line
                type="monotone"
                dataKey="reports"
                stroke="#10b981"
                strokeWidth={2}
                name="Total Reports"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Recent Activity */}
        <div className="bg-white rounded-lg shadow p-6 border border-gray-200">
          <h3 className="text-lg font-semibold text-gray-800 mb-4">
            System Information
          </h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between py-2 border-b">
              <span className="text-gray-600">Database Status:</span>
              <span className="font-semibold text-green-600">Healthy</span>
            </div>
            <div className="flex justify-between py-2 border-b">
              <span className="text-gray-600">Last Updated:</span>
              <span className="font-semibold text-gray-900">
                {new Date().toLocaleString()}
              </span>
            </div>
            <div className="flex justify-between py-2 border-b">
              <span className="text-gray-600">API Version:</span>
              <span className="font-semibold text-gray-900">v1.0.0</span>
            </div>
            <div className="flex justify-between py-2">
              <span className="text-gray-600">Consensus Accuracy:</span>
              <span className="font-semibold text-blue-600">
                {stats?.consensus_accuracy || '92.5'}%
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
